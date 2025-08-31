import kopf
import logging
import requests
import os
from kubernetes import client, config
from pydantic import BaseModel

# Track checkpointed pods
_ALREADY_CHECKPOINTED = set()

# Make sure client is usable inside cluster
config.load_incluster_config()
apps_api = client.AppsV1Api()
v1_api = client.CoreV1Api()

class PodSpecCheckpointRequest(BaseModel):
    pod_spec: dict


@kopf.on.event(
    'pods',
    labels={
        'snap.weaversoft.io/snap': kopf.PRESENT,   # key exists
        'snap.weaversoft.io/mutated': kopf.ABSENT # key does not exist
    },
)
async def on_pod_event(event, body, logger, **kwargs):
    evt_type = (event or {}).get("type") or "UNKNOWN"

    metadata = body.get("metadata", {}) or {}
    status   = body.get("status", {}) or {}
    spec     = body.get("spec", {}) or {}

    ns    = metadata.get("namespace", "-")
    name  = metadata.get("name", "-")
    uid   = metadata.get("uid")
    node_name = spec.get("nodeName", "-")   # <-- node name here

    # --- ignore deletions & terminating pods ---
    if evt_type == "DELETED" or metadata.get("deletionTimestamp"):
        return

    # Must be Running
    if status.get("phase") != "Running":
        return

    # Must report Ready=True
    conds = status.get("conditions", []) or []
    is_ready = any(c.get("type") == "Ready" and c.get("status") == "True" for c in conds)
    if not is_ready:
        return

    # At least one container started & running
    started = False
    for cs in status.get("containerStatuses", []) or []:
        state = cs.get("state", {}) or {}
        if "running" in state and cs.get("started"):
            started = True
            break
    if not started:
        return

    # --- reduce duplicates ---
    if uid in _ALREADY_CHECKPOINTED:
        return
    _ALREADY_CHECKPOINTED.add(uid)

    # Extract container name (first container)
    container_name = "-"
    containers = spec.get("containers") or []
    if containers:
        container_name = containers[0].get("name", "-")

    # --- resolve Deployment owner ---
    deployment_name = "-"
    owner_refs = metadata.get("ownerReferences", []) or []
    for ref in owner_refs:
        if ref.get("kind") == "ReplicaSet":
            rs_name = ref.get("name")
            try:
                rs = apps_api.read_namespaced_replica_set(rs_name, ns)
                for rs_owner in rs.metadata.owner_references or []:
                    if rs_owner.kind == "Deployment":
                        deployment_name = rs_owner.name
                        break
            except Exception as e:
                logger.warning(f"Failed to resolve Deployment from ReplicaSet {rs_name}: {e}")
        elif ref.get("kind") == "Deployment":
            deployment_name = ref.get("name")
            break

    print(
        f"Now we should checkpoint\n"
        f"  Event:      {evt_type}\n"
        f"  Namespace:  {ns}\n"
        f"  Deployment: {deployment_name}\n"
        f"  Pod:        {name}\n"
        f"  Container:  {container_name}\n"
        f"  Node:       {node_name}"
    )

    # -----------------------------------------------------------------
    # Send checkpoint request to SnapApi using new pod-spec endpoint
    # -----------------------------------------------------------------
    try:
        # Get SnapApi service URL from environment variable
        snap_api_url = os.getenv("SNAP_API_URL", "http://snapapi.snap.svc.cluster.local:8000")
        
        # Get authentication token from service account
        try:
            with open('/var/run/secrets/kubernetes.io/serviceaccount/token', 'r') as token_file:
                auth_token = token_file.read().strip()
        except FileNotFoundError:
            logger.error("Service account token not found")
            return
        
        # Prepare the complete pod specification for the request
        pod_spec_request = PodSpecCheckpointRequest(pod_spec=body)
        
        # Prepare headers with authentication
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}"
        }
        
        # Send request to new pod-spec checkpoint endpoint
        logger.info(f"Sending checkpoint request to SnapApi: {snap_api_url}")
        resp = requests.post(
            f"{snap_api_url}/checkpoint/pod-spec/checkpoint-and-push",
            json=pod_spec_request.dict(),
            headers=headers,
            timeout=120,  # Increased timeout for checkpoint operations
        )
        resp.raise_for_status()
        
        response_data = resp.json()
        logger.info(f"Checkpoint request sent successfully: {resp.status_code}")
        logger.info(f"Response: {response_data}")
        
        if response_data.get("success"):
            logger.info(f"Checkpoint and push completed successfully for pod {name}")
            logger.info(f"Image tag: {response_data.get('image_tag', 'N/A')}")
        else:
            logger.error(f"Checkpoint operation failed: {response_data.get('message', 'Unknown error')}")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send checkpoint request to SnapApi: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during checkpoint request: {e}")
