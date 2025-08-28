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

async def _detect_registry_type(registry_host: str, username: str = "", password: str = "") -> str:
    """
    Detect the type of registry by checking various endpoints.
    Returns: 'nexus', 'harbor', 'jfrog', 'dockerhub', 'docker-registry', or 'unknown'
    """
    print(f"[registry_detect] Detecting registry type for {registry_host}")
    
    # Common curl options
    base_curl_cmd = ["curl", "-s", "-k", "--connect-timeout", "10", "--max-time", "30"]
    
    # Add authentication if provided
    if username or password:
        base_curl_cmd.extend(["-u", f"{username}:{password}"])
    
    # Test endpoints for different registry types
    test_endpoints = [
        # Nexus Repository Manager
        {
            "type": "nexus",
            "endpoints": [
                f"https://{registry_host}/service/rest/v1/status",
                f"http://{registry_host}/service/rest/v1/status",
                f"https://{registry_host}/nexus/service/rest/v1/status"
            ]
        },
        # Harbor
        {
            "type": "harbor", 
            "endpoints": [
                f"https://{registry_host}/api/v2.0/systeminfo",
                f"http://{registry_host}/api/v2.0/systeminfo",
                f"https://{registry_host}/api/systeminfo"
            ]
        },
        # JFrog Artifactory
        {
            "type": "jfrog",
            "endpoints": [
                f"https://{registry_host}/artifactory/api/system/ping",
                f"http://{registry_host}/artifactory/api/system/ping",
                f"https://{registry_host}/api/system/ping"
            ]
        },
        # Docker Registry v2 API
        {
            "type": "docker-registry",
            "endpoints": [
                f"https://{registry_host}/v2/",
                f"http://{registry_host}/v2/"
            ]
        }
    ]
    
    # Check DockerHub specifically
    if registry_host.lower() in ["docker.io", "registry-1.docker.io", "index.docker.io"]:
        return "dockerhub"
    
    # Test each registry type
    for registry_test in test_endpoints:
        for endpoint in registry_test["endpoints"]:
            try:
                curl_cmd = base_curl_cmd + ["-o", "/dev/null", "-w", "%{http_code}", endpoint]
                result = await run(curl_cmd)
                http_code = result.stdout.strip() if result.stdout else ""
                
                print(f"[registry_detect] Testing {registry_test['type']} endpoint {endpoint}: HTTP {http_code}")
                
                # Consider 200, 401, 403 as valid responses (registry exists)
                if http_code in ["200", "401", "403"]:
                    print(f"[registry_detect] Detected registry type: {registry_test['type']}")
                    return registry_test["type"]
                    
            except Exception as e:
                print(f"[registry_detect] Error testing {endpoint}: {e}")
                continue
    
    print(f"[registry_detect] Could not detect registry type for {registry_host}, defaulting to docker-registry")
    return "docker-registry"

async def _check_image_exists_nexus(registry_host: str, repo: str, image_path: str, tag: str, username: str = "", password: str = "") -> bool:
    """Check image existence in Nexus Repository Manager"""
    print(f"[nexus_check] Checking image in Nexus: {registry_host}/{repo}/{image_path}:{tag}")
    
    # Nexus Docker registry API endpoints
    urls_to_try = [
        # Nexus v2 API
        f"https://{registry_host}/v2/{repo}/{image_path}/manifests/{tag}",
        f"http://{registry_host}/v2/{repo}/{image_path}/manifests/{tag}",
        # Nexus with repository prefix
        f"https://{registry_host}/repository/{repo}/v2/{image_path}/manifests/{tag}",
        f"http://{registry_host}/repository/{repo}/v2/{image_path}/manifests/{tag}",
    ]
    
    for url in urls_to_try:
        try:
            curl_cmd = ["curl", "-s", "-k", "-o", "/dev/null", "-w", "%{http_code}"]
            if username or password:
                curl_cmd.extend(["-u", f"{username}:{password}"])
            curl_cmd.append(url)
            
            result = await run(curl_cmd)
            http_code = result.stdout.strip() if result.stdout else ""
            print(f"[nexus_check] Testing {url}: HTTP {http_code}")
            
            if http_code == "200":
                return True
                
        except Exception as e:
            print(f"[nexus_check] Error checking {url}: {e}")
            continue
    
    return False

async def _check_image_exists_harbor(registry_host: str, repo: str, image_path: str, tag: str, username: str = "", password: str = "") -> bool:
    """Check image existence in Harbor"""
    print(f"[harbor_check] Checking image in Harbor: {registry_host}/{repo}/{image_path}:{tag}")
    
    urls_to_try = [
        # Harbor v2 API
        f"https://{registry_host}/v2/{repo}/{image_path}/manifests/{tag}",
        f"http://{registry_host}/v2/{repo}/{image_path}/manifests/{tag}",
        # Harbor API v2.0
        f"https://{registry_host}/api/v2.0/projects/{repo}/repositories/{image_path}/artifacts/{tag}",
        f"http://{registry_host}/api/v2.0/projects/{repo}/repositories/{image_path}/artifacts/{tag}",
    ]
    
    for url in urls_to_try:
        try:
            curl_cmd = ["curl", "-s", "-k", "-o", "/dev/null", "-w", "%{http_code}"]
            if username or password:
                curl_cmd.extend(["-u", f"{username}:{password}"])
            curl_cmd.append(url)
            
            result = await run(curl_cmd)
            http_code = result.stdout.strip() if result.stdout else ""
            print(f"[harbor_check] Testing {url}: HTTP {http_code}")
            
            if http_code == "200":
                return True
                
        except Exception as e:
            print(f"[harbor_check] Error checking {url}: {e}")
            continue
    
    return False

async def _check_image_exists_jfrog(registry_host: str, repo: str, image_path: str, tag: str, username: str = "", password: str = "") -> bool:
    """Check image existence in JFrog Artifactory"""
    print(f"[jfrog_check] Checking image in JFrog: {registry_host}/{repo}/{image_path}:{tag}")
    
    urls_to_try = [
        # JFrog Docker registry API
        f"https://{registry_host}/artifactory/api/docker/{repo}/v2/{image_path}/manifests/{tag}",
        f"http://{registry_host}/artifactory/api/docker/{repo}/v2/{image_path}/manifests/{tag}",
        # JFrog v2 API
        f"https://{registry_host}/v2/{repo}/{image_path}/manifests/{tag}",
        f"http://{registry_host}/v2/{repo}/{image_path}/manifests/{tag}",
    ]
    
    for url in urls_to_try:
        try:
            curl_cmd = ["curl", "-s", "-k", "-o", "/dev/null", "-w", "%{http_code}"]
            if username or password:
                curl_cmd.extend(["-u", f"{username}:{password}"])
            curl_cmd.append(url)
            
            result = await run(curl_cmd)
            http_code = result.stdout.strip() if result.stdout else ""
            print(f"[jfrog_check] Testing {url}: HTTP {http_code}")
            
            if http_code == "200":
                return True
                
        except Exception as e:
            print(f"[jfrog_check] Error checking {url}: {e}")
            continue
    
    return False

async def _check_image_exists_dockerhub(repo: str, image_path: str, tag: str, username: str = "", password: str = "") -> bool:
    """Check image existence in DockerHub"""
    print(f"[dockerhub_check] Checking image in DockerHub: {repo}/{image_path}:{tag}")
    
    # DockerHub API
    urls_to_try = [
        f"https://registry-1.docker.io/v2/{repo}/{image_path}/manifests/{tag}",
        f"https://index.docker.io/v2/{repo}/{image_path}/manifests/{tag}",
    ]
    
    for url in urls_to_try:
        try:
            curl_cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}"]
            if username or password:
                curl_cmd.extend(["-u", f"{username}:{password}"])
            curl_cmd.append(url)
            
            result = await run(curl_cmd)
            http_code = result.stdout.strip() if result.stdout else ""
            print(f"[dockerhub_check] Testing {url}: HTTP {http_code}")
            
            if http_code == "200":
                return True
                
        except Exception as e:
            print(f"[dockerhub_check] Error checking {url}: {e}")
            continue
    
    return False

async def _check_image_exists_docker_registry(registry_host: str, repo: str, image_path: str, tag: str, username: str = "", password: str = "") -> bool:
    """Check image existence in standard Docker Registry v2"""
    print(f"[docker_registry_check] Checking image in Docker Registry: {registry_host}/{repo}/{image_path}:{tag}")
    
    urls_to_try = [
        f"https://{registry_host}/v2/{repo}/{image_path}/manifests/{tag}",
        f"http://{registry_host}/v2/{repo}/{image_path}/manifests/{tag}",
    ]
    
    for url in urls_to_try:
        try:
            curl_cmd = ["curl", "-s", "-k", "-o", "/dev/null", "-w", "%{http_code}"]
            if username or password:
                curl_cmd.extend(["-u", f"{username}:{password}"])
            curl_cmd.append(url)
            
            result = await run(curl_cmd)
            http_code = result.stdout.strip() if result.stdout else ""
            print(f"[docker_registry_check] Testing {url}: HTTP {http_code}")
            
            if http_code == "200":
                return True
                
        except Exception as e:
            print(f"[docker_registry_check] Error checking {url}: {e}")
            continue
    
    return False

async def _check_image_exists_multi_registry(registry_host: str, repo: str, cluster: str, namespace: str, app: str, digest: str, pod_hash: str) -> bool:
    """
    Check if image exists across different registry types.
    Automatically detects registry type and uses appropriate API.
    """
    # Get credentials from environment variables
    username = os.getenv("snap_registry_user", "")
    password = os.getenv("snap_registry_pass", "")
    
    # Construct image path and tag
    image_path = f"{cluster}-{namespace}-{app}"
    tag = f"{digest}-{pod_hash}"
    
    print(f"[multi_registry_check] Checking image existence:")
    print(f"[multi_registry_check] Registry: {registry_host}")
    print(f"[multi_registry_check] Repo: {repo}")
    print(f"[multi_registry_check] Image path: {image_path}")
    print(f"[multi_registry_check] Tag: {tag}")
    print(f"[multi_registry_check] Using credentials: {'Yes' if username or password else 'No'}")
    
    try:
        # Detect registry type
        registry_type = await _detect_registry_type(registry_host, username, password)
        print(f"[multi_registry_check] Detected registry type: {registry_type}")
        
        # Check image existence based on registry type
        if registry_type == "nexus":
            return await _check_image_exists_nexus(registry_host, repo, image_path, tag, username, password)
        elif registry_type == "harbor":
            return await _check_image_exists_harbor(registry_host, repo, image_path, tag, username, password)
        elif registry_type == "jfrog":
            return await _check_image_exists_jfrog(registry_host, repo, image_path, tag, username, password)
        elif registry_type == "dockerhub":
            return await _check_image_exists_dockerhub(repo, image_path, tag, username, password)
        else:  # docker-registry or unknown
            return await _check_image_exists_docker_registry(registry_host, repo, image_path, tag, username, password)
            
    except Exception as e:
        print(f"[multi_registry_check] Error during image existence check: {e}")
        logger.warning(f"Error checking image existence: {str(e)}")
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
        
        print(f"[config] Using snap_registry from env: {snap_registry}")
        print(f"[config] Using snap_repo from env: {snap_repo}")

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

        # Pretty echo
        print(
            "-----------------------------------------------------------------------------\n"
            "Received pod webhook data from:\n"
            f"- cluster: {data.cluster_name}\n"
            f"- namespace: {namespace}\n"
            f"- app: {app}\n"
            f"- origImageShortDigest: {orig_image_short_digest}\n"
            f"- PodTemplateHash: {pod_template_hash}\n"
            f"- original_registry: {registry}\n"
            f"- original_repo: {repo}\n"
            f"- snap_registry: {snap_registry}\n"
            f"- snap_repo: {snap_repo}\n"
            f"- generated_image_tag: {generated_image_tag}\n"
            "-----------------------------------------------------------------------------"
        )

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
