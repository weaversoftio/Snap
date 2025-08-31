from fastapi import APIRouter, HTTPException
from flows.proccess_utils import run
from flows.k8s.migrate_pod import PodMigrationRequest, migrate_pod
import subprocess
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
import os
import json
import logging
import glob
import re
from classes.imagetag import generate_image_tag, parse_image_tag, get_image_component

logger = logging.getLogger(__name__)
router = APIRouter()

class PodWebhookData(BaseModel):
    cluster_name: str
    pod_data: Dict[Any, Any]


# ------------------ helpers ------------------

def _strip_sha_repo(digest: str, short: bool = True) -> str:
    """
    Return the digest without the 'sha256:' repo.
    If short=True, also truncate to first 12 chars.
    """
    if not digest:
        return "unknown"
    # Remove sha256: repo if present
    digest = digest.split("sha256:", 1)[-1] if digest.startswith("sha256:") else digest
    return digest[:12] if short else digest

def _pick_digest_from_image_id(image_id: str) -> Optional[str]:
    """
    Normalize common CRI imageID formats to the digest string (sha256:...).
    Examples we may see:
      docker-pullable://docker.io/library/nginx@sha256:abc...
      containerd://sha256:abc...
      docker://sha256:abc...
      docker.io/library/nginx@sha256:abc...
    """
    if not image_id:
        return None
    if "@" in image_id:
        # everything after '@' is typically 'sha256:...'
        return image_id.split("@", 1)[-1]
    sha_idx = image_id.find("sha256:")
    if sha_idx != -1:
        return image_id[sha_idx:]  # returns 'sha256:...'
    return None

def _extract_digest_from_pod_obj(pod: Dict[str, Any], prefer_container_name: Optional[str] = None) -> Optional[str]:
    """
    Try to read the digest from a pod object already containing status.
    If prefer_container_name is given, pick that container; otherwise use the first container.
    Returns either 'sha256:...' or a digest pinned in spec (after '@'), or None if not found.
    """
    statuses: List[Dict[str, Any]] = (pod.get("status", {}) or {}).get("containerStatuses", []) or []
    if statuses:
        chosen = None
        if prefer_container_name:
            for st in statuses:
                if st.get("name") == prefer_container_name:
                    chosen = st
                    break
        if not chosen:
            chosen = statuses[0]
        digest = _pick_digest_from_image_id(chosen.get("imageID", "") or "")
        if digest:
            return digest

    # rare: spec image pinned by digest (e.g., repo@sha256:...)
    containers: List[Dict[str, Any]] = (pod.get("spec", {}) or {}).get("containers", []) or []
    if containers:
        target = None
        if prefer_container_name:
            for c in containers:
                if c.get("name") == prefer_container_name:
                    target = c
                    break
        if not target:
            target = containers[0]
        image_ref = target.get("image", "") or ""
        if "@" in image_ref:
            return image_ref.split("@", 1)[-1]

    return None

def _parse_registry_host_from_image(image: str) -> str:
    """
    Extract the registry host from an image reference.
    - If the first path segment contains '.' or ':' or equals 'localhost', treat it as a registry host.
    - Otherwise default to 'docker.io'.
    """
    if not image or "/" not in image:
        return "docker.io"

    first = image.split("/", 1)[0]
    if "." in first or ":" in first or first == "localhost":
        return first
    return "docker.io"

def _normalize_registry_host(val: str) -> str:
    """
    Normalize registry host strings for comparison:
    - strip scheme (http[s]://)
    - trim trailing slashes/whitespace
    - lowercase host portion (safe for hostnames; ports unaffected)
    """
    if not val:
        return ""
    # Remove scheme if present
    val = re.sub(r"^[a-z]+://", "", val.strip(), flags=re.IGNORECASE)
    # Drop any trailing slash
    val = val.rstrip("/")
    return val.lower()

def _find_registry_creds(registry_host: str, base_dir: str = "/app/config/registry") -> Optional[Dict[str, str]]:
    """
    Scan all JSON files in base_dir for a matching registry host.
    Match against `registry_config_details.registry` first, then `name`.
    Returns dict with username/password if found (even if one is empty), else None.
    """
    try:
        target = _normalize_registry_host(registry_host)
        pattern = os.path.join(base_dir, "*.json")
        for path in glob.glob(pattern):
            try:
                with open(path, "r") as f:
                    cfg = json.load(f) or {}
                details = (cfg.get("registry_config_details") or {})
                # prefer explicit `registry` field; fallback to `name`
                reg_val = details.get("registry") or cfg.get("name") or ""
                if _normalize_registry_host(reg_val) == target:
                    username = (details.get("username") or "").strip()
                    password = (details.get("password") or "").strip()
                    print(f"Registry config found: {registry_host}")
                    return {"username": username, "password": password}
            except Exception as e:
                print(f"Config parse error: {path}")
    except Exception as e:
        print(f"Registry scan error: {base_dir}")
    return None

async def _resolve_digest_with_skopeo(image_url: str) -> str:
    if not image_url:
        print("No image URL provided")
        return "unknown"

    registry_host = _parse_registry_host_from_image(image_url)
    print(f"Resolving digest: {image_url}")

    creds = None
    cred_obj = _find_registry_creds(registry_host)
    if cred_obj is not None:
        username = cred_obj.get("username", "")
        password = cred_obj.get("password", "")
        if username or password:
            creds = f"{username}:{password}"
            print(f"Using credentials for {registry_host}")

    cmd = ["skopeo", "inspect"]
    if creds:
        cmd += ["--creds", creds]
    cmd += ["docker://" + image_url]

    try:
        proc = await run(cmd)
        if proc.returncode == 0 and proc.stdout:
            data = json.loads(proc.stdout)
            digest_full = data.get("Digest", "")
            print(f"Digest resolved: {digest_full[:19]}...")
            return _strip_sha_repo(digest_full) if digest_full else "unknown"
    except Exception as e:
        print(f"Skopeo error: {e}")

    return "unknown"

async def _extract_digest(pod: Dict[str, Any]) -> str:
    spec = pod.get("spec", {}) or {}
    containers: List[Dict[str, Any]] = (spec.get("containers", []) or [])
    prefer_container_name = containers[0].get("name") if containers else None

    # Step 1: try from pod.status.containerStatuses
    in_pod = _extract_digest_from_pod_obj(pod, prefer_container_name)
    if in_pod:
        print(f"Digest from pod status: {_strip_sha_repo(in_pod)}")
        return _strip_sha_repo(in_pod)

    # Step 2: fallback to skopeo
    image_ref = containers[0].get("image", "") if containers else ""
    if image_ref:
        digest = await _resolve_digest_with_skopeo(image_ref)
        return digest

    print("No digest found")
    return "unknown"


async def _check_image_exists_multi_registry(registry_host: str, repo: str, cluster: str, namespace: str, app: str, digest: str, pod_hash: str) -> bool:
    """
    Check if image exists using skopeo inspect command.
    This replaces the previous curl-based registry-specific implementations.
    """
    # Construct image path and tag (convert to lowercase for Docker registry compatibility)
    image_path = f"{cluster}-{namespace}-{app}".lower()
    tag = f"{digest}-{pod_hash}".lower()
    
    # Construct full image reference
    if repo:
        full_image_ref = f"{registry_host}/{repo}/{image_path}:{tag}"
    else:
        full_image_ref = f"{registry_host}/{image_path}:{tag}"
    
    print(f"Checking image: {full_image_ref}")
    
    try:
        # Find credentials for this registry
        creds = None
        cred_obj = _find_registry_creds(registry_host)
        if cred_obj is not None:
            username = cred_obj.get("username", "")
            password = cred_obj.get("password", "")
            if username or password:
                creds = f"{username}:{password}"
                print(f"Using registry credentials")
        
        # Also check environment variables as fallback
        if not creds:
            env_username = os.getenv("snap_registry_user", "")
            env_password = os.getenv("snap_registry_pass", "")
            if env_username or env_password:
                creds = f"{env_username}:{env_password}"
                print(f"Using env credentials")
        
        # Build skopeo command
        cmd = ["skopeo", "inspect", "--insecure-policy", "--tls-verify=false"]
        if creds:
            cmd += ["--creds", creds]
        cmd += ["docker://" + full_image_ref]
        
        # Execute skopeo inspect
        result = await run(cmd)
        
        # If skopeo inspect succeeds (return code 0), the image exists
        if result.returncode == 0:
            print(f"Image exists")
            return True
        else:
            print(f"Image not found")
            return False
            
    except Exception as e:
        print(f"Image check error: {e}")
        logger.warning(f"Error checking image existence with skopeo: {str(e)}")
        return False


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
        app = labels.get("app", "unknown")
        pod_template_hash = labels.get("pod-template-hash", "unknown")

        # Resolve digest (without 'sha256:' repo), or 'unknown'
        orig_image_short_digest = await _extract_digest(pod)

        # Extract registry and repo from the first container's image
        containers = spec.get("containers", [])
        registry = "docker.io"  # default
        repo = ""  # default
        if containers:
            image_ref = containers[0].get("image", "")
            registry = _parse_registry_host_from_image(image_ref)
            
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

        # Get registry and repo from environment variables for generated image tag
        snap_registry = os.getenv("snap_registry", "docker.io")
        snap_repo = os.getenv("snap_repo", "snap")
        
        print(f"Registry config: {snap_registry}/{snap_repo}")

        # Generate the complete image tag using environment variables
        generated_image_tag = None
        try:
            generated_image_tag = generate_image_tag(
                registry=snap_registry,
                repo=snap_repo,
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

        # Check if the generated image exists in the registry using environment variables
        image_exists = await _check_image_exists_multi_registry(
            snap_registry, snap_repo, data.cluster_name, namespace, app, 
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
