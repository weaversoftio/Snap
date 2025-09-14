import json
import os
import glob
import re
import logging
from typing import Any, Dict, Optional, List
from flows.proccess_utils import run

logger = logging.getLogger(__name__)


def _short_digest_from_full(full_digest: str) -> str:
    """
    full_digest like 'sha256:4833e2f3ecd4a163...'
    returns '4833e2f3ecd4'
    """
    if not full_digest:
        return ""
    try:
        return full_digest.split(":")[-1][:12]
    except Exception:
        return full_digest[:12]


async def _skopeo_extract_digest(image_ref: str) -> str:
    """
    image_ref example: docker://docker.io/nginxinc/nginx-unprivileged:stable
    returns full digest like 'sha256:4833e2f3...'
    """
    cmd = ["skopeo", "inspect", image_ref]
    out = await run(cmd)
    data = json.loads(out.stdout)
    return data.get("Digest", "")


def strip_sha_repo(digest: str, short: bool = True) -> str:
    """
    Return the digest without the 'sha256:' repo.
    If short=True, also truncate to first 12 chars.
    """
    if not digest:
        return "unknown"
    # Remove sha256: repo if present
    digest = digest.split("sha256:", 1)[-1] if digest.startswith("sha256:") else digest
    return digest[:12] if short else digest


def pick_digest_from_image_id(image_id: str) -> Optional[str]:
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


def extract_digest_from_pod_obj(pod: Dict[str, Any], prefer_container_name: Optional[str] = None) -> Optional[str]:
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
        digest = pick_digest_from_image_id(chosen.get("imageID", "") or "")
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


def parse_registry_host_from_image(image: str) -> str:
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


def normalize_registry_host(val: str) -> str:
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


def find_registry_creds(registry_host: str, base_dir: str = "/app/config/registry") -> Optional[Dict[str, str]]:
    """
    Scan all JSON files in base_dir for a matching registry host.
    Match against `registry_config_details.registry` first, then `name`.
    Returns dict with username/password if found (even if one is empty), else None.
    """
    try:
        target = normalize_registry_host(registry_host)
        pattern = os.path.join(base_dir, "*.json")
        for path in glob.glob(pattern):
            try:
                with open(path, "r") as f:
                    cfg = json.load(f) or {}
                details = (cfg.get("registry_config_details") or {})
                # prefer explicit `registry` field; fallback to `name`
                reg_val = details.get("registry") or cfg.get("name") or ""
                if normalize_registry_host(reg_val) == target:
                    username = (details.get("username") or "").strip()
                    password = (details.get("password") or "").strip()
                    print(f"Registry config found: {registry_host}")
                    return {"username": username, "password": password}
            except Exception as e:
                print(f"Config parse error: {path}")
    except Exception as e:
        print(f"Registry scan error: {base_dir}")
    return None


async def resolve_digest_with_skopeo(image_url: str) -> str:
    if not image_url:
        print("No image URL provided")
        return "unknown"

    registry_host = parse_registry_host_from_image(image_url)
    print(f"Resolving digest: {image_url}")

    creds = None
    cred_obj = find_registry_creds(registry_host)
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
            return strip_sha_repo(digest_full) if digest_full else "unknown"
    except Exception as e:
        print(f"Skopeo error: {e}")

    return "unknown"


async def extract_digest(pod: Dict[str, Any]) -> str:
    spec = pod.get("spec", {}) or {}
    containers: List[Dict[str, Any]] = (spec.get("containers", []) or [])
    prefer_container_name = containers[0].get("name") if containers else None

    # Step 1: try from pod.status.containerStatuses
    in_pod = extract_digest_from_pod_obj(pod, prefer_container_name)
    if in_pod:
        print(f"Digest from pod status: {strip_sha_repo(in_pod)}")
        return strip_sha_repo(in_pod)

    # Step 2: fallback to skopeo
    image_ref = containers[0].get("image", "") if containers else ""
    if image_ref:
        digest = await resolve_digest_with_skopeo(image_ref)
        return digest

    print("No digest found")
    return "unknown"


def extract_app_name_from_pod(pod_name: str, labels: Dict[str, Any]) -> str:
    """
    Extract app name from pod name and labels using multiple strategies.
    
    Args:
        pod_name: The name of the pod
        labels: Dictionary of pod labels
        
    Returns:
        Extracted app name string
    """
    app = ""
    
    if pod_name:
        # Strategy 1: Try to get app from labels first
        app = (
            labels.get("app.kubernetes.io/name") or
            labels.get("app") or
            labels.get("k8s-app") or
            labels.get("app.kubernetes.io/instance") or
            ""
        )
        
        # Strategy 2: If no app label, extract from pod name
        if not app:
            # Remove Kubernetes hash suffixes: -XXXXXXXXX-XXXXX or -XXXXXXXXX
            app = re.sub(r'-[a-zA-Z0-9]{8,10}(-[a-zA-Z0-9]{5})?$', '', pod_name)
            
            # Strategy 3: If still empty, try other common patterns
            if not app:
                # Try removing just the last hash part (e.g., deployment-name-hash -> deployment-name)
                app = re.sub(r'-[a-zA-Z0-9]{8,}$', '', pod_name)
            
            # Strategy 4: If still empty, try extracting first meaningful part
            if not app:
                # Split by hyphens and take first 1-2 parts that aren't just numbers/hashes
                parts = pod_name.split('-')
                meaningful_parts = []
                for part in parts:
                    # Skip parts that look like hashes (all alphanumeric, 5+ chars)
                    if not (len(part) >= 5 and part.isalnum() and any(c.isdigit() for c in part)):
                        meaningful_parts.append(part)
                    else:
                        break  # Stop at first hash-like part
                
                if meaningful_parts:
                    app = '-'.join(meaningful_parts[:2])  # Take first 1-2 meaningful parts
            
            # Strategy 5: Final fallback - use the full pod name if nothing else worked
            if not app:
                app = pod_name
    
    # Last resort fallback
    if not app:
        app = "unknown-app"
    
    return app


async def check_image_exists_multi_registry(registry_host: str, repo: str, cluster: str, namespace: str, app: str, digest: str, pod_hash: str) -> bool:
    """
    Check if image exists using skopeo inspect command.
    This replaces the previous curl-based registry-specific implementations.
    """
    # Construct image path and tag (convert to lowercase for Docker registry compatibility)
    # This must match the logic in imagetag.py generate_tag() method
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
        cred_obj = find_registry_creds(registry_host)
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


def load_cluster_cache_config(cluster_cache: str) -> Dict[str, Any]:
    """
    Load cluster cache configuration from /config/clusterCache/{cluster_cache}.json
    
    Args:
        cluster_cache: The cluster name to load configuration for
        
    Returns:
        Dictionary containing cluster cache configuration
        
    Raises:
        ValueError: If cluster cache configuration is not found
    """
    cluster_cache_path = f"config/clusterCache/{cluster_cache}.json"
    if not os.path.exists(cluster_cache_path):
        raise ValueError(f"Cluster cache configuration not found for cluster: {cluster_cache}")
    
    with open(cluster_cache_path, 'r') as f:
        cluster_cache_data = json.load(f)
    
    return cluster_cache_data


def load_registry_config(registry_name: str) -> Dict[str, str]:
    """
    Load registry configuration from /config/registry/{registry_name}.json
    
    Args:
        registry_name: The registry name to load configuration for
        
    Returns:
        Dictionary containing registry configuration (registry, username, password)
        
    Raises:
        ValueError: If registry configuration is not found
    """
    registry_path = f"config/registry/{registry_name}.json"
    if not os.path.exists(registry_path):
        raise ValueError(f"Registry configuration not found: {registry_name}")
    
    with open(registry_path, 'r') as f:
        registry_data = json.load(f)
    
    return {
        "registry": registry_data["registry_config_details"]["registry"],
        "username": registry_data["registry_config_details"]["username"],
        "password": registry_data["registry_config_details"]["password"]
    }


def load_cluster_config(cluster_name: str) -> str:
    """
    Load cluster configuration from /config/clusters/{cluster_name}.json
    
    Args:
        cluster_name: The cluster name to load configuration for
        
    Returns:
        The kube API URL from cluster configuration
        
    Raises:
        ValueError: If cluster configuration is not found
    """
    cluster_path = f"config/clusters/{cluster_name}.json"
    if not os.path.exists(cluster_path):
        raise ValueError(f"Cluster configuration not found: {cluster_name}")
    
    with open(cluster_path, 'r') as f:
        cluster_data = json.load(f)
    
    return cluster_data["cluster_config_details"]["kube_api_url"]


def get_snap_config_from_cluster_cache(cluster_cache: str) -> Dict[str, str]:
    """
    Get all snap configuration values from cluster cache, registry, and cluster configs.
    
    Args:
        cluster_cache: The cluster name to load configuration for
        
    Returns:
        Dictionary containing all snap configuration values:
        - cache_registry: Registry URL
        - cache_registry_user: Registry username
        - cache_registry_pass: Registry password
        - cache_repo: Repository name
        - kube_api_address: Kubernetes API address
        - token: Kubernetes authentication token
        
    Raises:
        ValueError: If any required configuration is not found
    """
    # Load cluster cache configuration
    cluster_cache_data = load_cluster_cache_config(cluster_cache)
    
    # Extract registry, cluster, and repo names from cluster cache
    registry_name = cluster_cache_data["cluster_cache_details"]["registry"]
    cluster_name = cluster_cache_data["cluster_cache_details"]["cluster"]
    cache_repo = cluster_cache_data["cluster_cache_details"]["repo"]
    
    # Load registry configuration
    registry_config = load_registry_config(registry_name)
    
    # Load cluster configuration
    kube_api_address = load_cluster_config(cluster_name)
    
    # Load cluster authentication details
    cluster_config_path = f"config/clusters/{cluster_name}.json"
    
    with open(cluster_config_path, 'r') as f:
        cluster_config_data = json.load(f)
    
    cluster_auth = cluster_config_data["cluster_config_details"]
    
    return {
        "cache_registry": registry_config["registry"],
        "cache_registry_user": registry_config["username"],
        "cache_registry_pass": registry_config["password"],
        "cache_repo": cache_repo,
        "kube_api_address": kube_api_address,
        "token": cluster_auth.get("token", "")
    }


async def get_snap_config_from_cluster_cache_api(cluster_cache: str) -> Dict[str, str]:
    """
    Get all snap configuration values from cluster cache using the API endpoint.
    
    Args:
        cluster_cache: The cluster name to load configuration for
        
    Returns:
        Dictionary containing all snap configuration values:
        - cache_registry: Registry URL
        - cache_registry_user: Registry username
        - cache_registry_pass: Registry password
        - cache_repo: Repository name
        - kube_api_address: Kubernetes API address
        - token: Kubernetes authentication token
        
    Raises:
        ValueError: If any required configuration is not found
    """
    from flows.config.clusterCache.get_cluster_cache import get_cluster_cache
    
    # Get cluster cache configuration using API
    cluster_cache_response = await get_cluster_cache(cluster_cache)
    
    if not cluster_cache_response.success:
        raise ValueError(f"Failed to get cluster cache: {cluster_cache_response.message}")
    
    cluster_cache_details = cluster_cache_response.cluster_cache_details
    
    # Extract registry, cluster, and repo names from cluster cache
    registry_name = cluster_cache_details.registry
    cluster_name = cluster_cache_details.cluster
    cache_repo = cluster_cache_details.repo
    
    # Load registry configuration
    registry_config = load_registry_config(registry_name)
    
    # Load cluster configuration
    kube_api_address = load_cluster_config(cluster_name)
    
    # Load cluster authentication details
    cluster_data = load_cluster_cache_config(cluster_cache)
    cluster_name_from_cache = cluster_data["cluster_cache_details"]["cluster"]
    cluster_config_path = f"config/clusters/{cluster_name_from_cache}.json"
    
    with open(cluster_config_path, 'r') as f:
        cluster_config_data = json.load(f)
    
    cluster_auth = cluster_config_data["cluster_config_details"]
    
    return {
        "cache_registry": registry_config["registry"],
        "cache_registry_user": registry_config["username"],
        "cache_registry_pass": registry_config["password"],
        "cache_repo": cache_repo,
        "kube_api_address": kube_api_address,
        "token": cluster_auth.get("token", "")
    }
