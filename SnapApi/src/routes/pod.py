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
                    print(f"[skopeo] Matched registry config: {path} for host {registry_host}")
                    return {"username": username, "password": password}
            except Exception as e:
                print(f"[skopeo] Could not parse config {path}: {e}")
    except Exception as e:
        print(f"[skopeo] Error scanning registry configs in {base_dir}: {e}")
    return None

async def _resolve_digest_with_skopeo(image_url: str) -> str:
    if not image_url:
        print("[skopeo] No image_url provided")
        return "unknown"

    registry_host = _parse_registry_host_from_image(image_url)

    print(f"[skopeo] Trying to resolve digest for image: {image_url}")
    print(f"[skopeo] Looking for configs under /app/config/registry matching host: {registry_host}")

    creds = None
    cred_obj = _find_registry_creds(registry_host)
    if cred_obj is not None:
        username = cred_obj.get("username", "")
        password = cred_obj.get("password", "")
        if username or password:
            creds = f"{username}:{password}"
            print(f"[skopeo] Found credentials for {registry_host}: {username}/***")

    cmd = ["skopeo", "inspect"]
    if creds:
        cmd += ["--creds", creds]
    cmd += ["docker://" + image_url]

    print(f"[skopeo] Running: {' '.join(cmd)}")

    try:
        proc = await run(cmd)
        print(f"[skopeo] Return code: {proc.returncode}")
        if proc.stdout:
            print(f"[skopeo] STDOUT: {proc.stdout[:500]}")  # truncate long output
        if proc.stderr:
            print(f"[skopeo] STDERR: {proc.stderr[:500]}")

        if proc.returncode == 0 and proc.stdout:
            data = json.loads(proc.stdout)
            digest_full = data.get("Digest", "")
            print(f"[skopeo] Parsed Digest: {digest_full}")
            return _strip_sha_repo(digest_full) if digest_full else "unknown"
    except Exception as e:
        print(f"[skopeo] Exception running skopeo: {e}")

    return "unknown"

async def _extract_digest(pod: Dict[str, Any]) -> str:
    print("[digest] Starting _extract_digest")

    spec = pod.get("spec", {}) or {}
    containers: List[Dict[str, Any]] = (spec.get("containers", []) or [])
    prefer_container_name = containers[0].get("name") if containers else None
    print(f"[digest] Containers found: {[c.get('name') for c in containers]}")

    # Step 1: try from pod.status.containerStatuses
    in_pod = _extract_digest_from_pod_obj(pod, prefer_container_name)
    print(f"[digest] From containerStatuses/spec pinned: {in_pod}")
    if in_pod:
        return _strip_sha_repo(in_pod)

    # Step 2: fallback to skopeo
    image_ref = containers[0].get("image", "") if containers else ""
    print(f"[digest] Image ref for skopeo: {image_ref}")

    if image_ref:
        digest = await _resolve_digest_with_skopeo(image_ref)
        print(f"[digest] Result from skopeo: {digest}")
        return digest

    print("[digest] No containers/image found in pod")
    return "unknown"


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

        # Extract registry from the first container's image
        containers = spec.get("containers", [])
        registry = "docker.io"  # default
        if containers:
            image_ref = containers[0].get("image", "")
            registry = _parse_registry_host_from_image(image_ref)

        # Use "snap" as default repo - could be made configurable
        repo = "snap"

        # Generate the complete image tag using our ImageTag class
        generated_image_tag = None
        try:
            generated_image_tag = generate_image_tag(
                registry=registry,
                repo=repo,
                cluster=data.cluster_name,
                namespace=namespace,
                app=app,
                origImageShortDigest=orig_image_short_digest,
                PodTemplateHash=pod_template_hash
            )
        except Exception as tag_error:
            logger.warning(f"Failed to generate image tag: {tag_error}")
            generated_image_tag = "generation-failed"

        # Pretty echo
        print(
            "-----------------------------------------------------------------------------\n"
            "Received pod webhook data from:\n"
            f"- cluster: {data.cluster_name}\n"
            f"- namespace: {namespace}\n"
            f"- app: {app}\n"
            f"- origImageShortDigest: {orig_image_short_digest}\n"
            f"- PodTemplateHash: {pod_template_hash}\n"
            f"- registry: {registry}\n"
            f"- repo: {repo}\n"
            f"- generated_image_tag: {generated_image_tag}\n"
            "-----------------------------------------------------------------------------"
        )

        return {
            "status": "success",
            "message": f"Pod data received from cluster {data.cluster_name}",
            "pod_name": meta.get("name", "unknown"),
            "pod_namespace": namespace,
            "origImageShortDigest": orig_image_short_digest,
            "app": app,
            "podTemplateHash": pod_template_hash,
            "registry": registry,
            "repo": repo,
            "generated_image_tag": generated_image_tag,
        }

    except Exception as e:
        logger.error(f"Error processing pod webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing webhook: {str(e)}")
