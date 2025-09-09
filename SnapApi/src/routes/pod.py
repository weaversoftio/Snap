from fastapi import APIRouter, HTTPException
from flows.proccess_utils import run
from flows.k8s.migrate_pod import PodMigrationRequest, migrate_pod
from flows.helpers import (
    strip_sha_repo, pick_digest_from_image_id, extract_digest_from_pod_obj,
    parse_registry_host_from_image, normalize_registry_host, find_registry_creds,
    resolve_digest_with_skopeo, extract_digest, check_image_exists_multi_registry,
    extract_app_name_from_pod, get_snap_config_from_cluster_cache
)
import subprocess
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
import os
import json
import logging
from classes.imagetag import generate_image_tag, parse_image_tag, get_image_component

logger = logging.getLogger(__name__)
router = APIRouter()

class PodWebhookData(BaseModel):
    cluster_name: str
    pod_data: Dict[Any, Any]


# ------------------ endpoints ------------------

@router.get("/list")
async def list_pods():
    try:
        list_pods_cmd = ["kubectl", "get", "pods", "-A", "--output", "json"]
        result = await run(list_pods_cmd)

        if result.returncode == 0:
            return {"pods": result.stdout}
        else:
            # Fixed: use HTTPException (typo previously HTTPEngineError)
            raise HTTPException(status_code=500, detail="Failed to list pods")
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error executing kubectl command: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.post("/migrate")
async def MigratePod(request: PodMigrationRequest):
    try:
        result = await migrate_pod(request)
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.post("/webhook")
async def receive_pod_webhook(data: PodWebhookData):
    try:
        pod = data.pod_data or {}
        meta = pod.get("metadata", {}) or {}
        spec = pod.get("spec", {}) or {}

        namespace = meta.get("namespace", "unknown")
        labels = meta.get("labels", {}) or {}
        pod_name = meta.get("name", "unknown")
        
        # If pod_name is "unknown", try to use generateName
        if pod_name == "unknown":
            generate_name = meta.get("generateName", "")
            if generate_name:
                # Remove trailing dash from generateName
                pod_name = generate_name.rstrip("-")
                print(f"DEBUG - Using generateName: '{generate_name}' -> pod_name: '{pod_name}'")
        
        print(f"DEBUG - Webhook received pod_name: '{pod_name}', namespace: '{namespace}'")
        print(f"DEBUG - Webhook received labels: {labels}")
        
        # Extract app name using helper function
        app = extract_app_name_from_pod(pod_name, labels)
        print(f"DEBUG - Extracted app name: '{app}'")
        
        # Use "unknown" as fallback for webhook (instead of "unknown-app")
        if app == "unknown-app":
            app = "unknown"
        
        pod_template_hash = labels.get("pod-template-hash", "unknown")

        # Resolve digest (without 'sha256:' repo), or 'unknown'
        orig_image_short_digest = await extract_digest(pod)

        # Extract registry and repo from the first container's image
        containers = spec.get("containers", [])
        registry = "docker.io"  # default
        repo = ""  # default
        if containers:
            image_ref = containers[0].get("image", "")
            registry = parse_registry_host_from_image(image_ref)
            
            # Parse repo from image_ref
            try:
                # Remove registry part and extract repo
                if "/" in image_ref:
                    # Handle cases like:
                    # docker.io/library/nginx -> repo = library
                    # quay.io/myorg/myapp -> repo = myorg
                    # registry.com/path/to/repo -> repo = path
                    parts = image_ref.split("/")
                    if len(parts) >= 2:
                        # Skip registry part (first part) and take the next part as repo
                        repo = parts[1]
                        # Handle special case for docker.io/library -> use "library"
                        if registry == "docker.io" and repo == "library" and len(parts) >= 3:
                            repo = parts[2].split(":")[0].split("@")[0]  # Remove tag/digest
                        else:
                            repo = repo.split(":")[0].split("@")[0]  # Remove tag/digest
            except Exception as e:
                logger.warning(f"Failed to parse repo from image_ref {image_ref}: {e}")
                repo = ""  # fallback to default

        # Get registry and repo from cluster cache configuration
        try:
            snap_config = get_snap_config_from_cluster_cache(data.cluster_name)
            cache_registry = snap_config["cache_registry"]
            cache_repo = snap_config["cache_repo"]
        except Exception as e:
            logger.warning(f"Failed to load cluster cache config for {data.cluster_name}: {e}")
            # Fallback to environment variables
            cache_registry = os.getenv("snap_registry", "docker.io")
            cache_repo = os.getenv("snap_repo", "snap")
        
        print(f"Registry config: {cache_registry}/{cache_repo}")

        # Generate the complete image tag using cluster cache configuration
        generated_image_tag = None
        try:
            generated_image_tag = generate_image_tag(
                registry=cache_registry,
                repo=cache_repo,
                cluster=data.cluster_name,
                namespace=namespace,
                app=app,
                origImageShortDigest=orig_image_short_digest,
                PodTemplateHash=pod_template_hash
            )
        except Exception as tag_error:
            logger.warning(f"Failed to generate image tag: {tag_error}")
            generated_image_tag = "generation-failed"

        print(f"Pod webhook: {data.cluster_name}/{namespace}/{app} | digest:{orig_image_short_digest} | tag:{generated_image_tag}")

        # Check if the generated image exists in the registry using cluster cache configuration
        image_exists = await check_image_exists_multi_registry(
            cache_registry, cache_repo, data.cluster_name, namespace, app, 
            orig_image_short_digest, pod_template_hash
        )

        # Return response based on image existence
        if image_exists:
            return {
                "exist": "True",
                "generated_image_tag": generated_image_tag
            }
        else:
            return {
                "exist": "False"
            }

    except Exception as e:
        logger.error(f"Error processing pod webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing webhook: {str(e)}")
