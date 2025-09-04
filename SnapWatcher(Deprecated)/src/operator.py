import kopf
import requests
import os
from kubernetes import client, config
from pydantic import BaseModel


# Make sure client is usable inside cluster
config.load_incluster_config()
apps_api = client.AppsV1Api()
v1_api = client.CoreV1Api()

class PodSpecCheckpointRequest(BaseModel):
    pod_spec: dict


@kopf.on.event(
    'pods',
    labels={
        'snap.weaversoft.io/snap': kopf.PRESENT,   
        'snap.weaversoft.io/mutated': kopf.ABSENT 
    },
)
async def on_pod_event(event, body, logger, **kwargs):
    evt_type = (event or {}).get("type") or "UNKNOWN"

    metadata = body.get("metadata", {}) or {}
    status   = body.get("status", {}) or {}
    spec     = body.get("spec", {}) or {}

    ns    = metadata.get("namespace", "-")
    pod  = metadata.get("name", "-")
    node_name = spec.get("nodeName", "-")   

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

    # Extract container name (first container)
    container_name = "-"
    containers = spec.get("containers") or []
    if containers:
        container_name = containers[0].get("name", "-")


    print(
        f"Now we should checkpoint\n"
        f"  Event:      {evt_type}\n"
        f"  Namespace:  {ns}\n"
        f"  Pod:        {pod}\n"
        f"  Container:  {container_name}\n"
        f"  Node:       {node_name}"
    )

    # -----------------------------------------------------------------
    # Send checkpoint request to SnapApi using new pod-spec endpoint
    # -----------------------------------------------------------------
    try:
        # Get SnapApi service URL from environment variable
        snap_api_url = os.getenv("SNAP_API_URL", "http://snapapi.snap.svc.cluster.local:8000")
        
        # Prepare the complete pod specification for the request
        pod_spec_request = PodSpecCheckpointRequest(pod_spec=body)
        
        # Send request to new pod-spec checkpoint endpoint
        logger.info(f"Sending checkpoint request to SnapApi: {snap_api_url}")
        resp = requests.post(
            f"{snap_api_url}/checkpoint/pod-spec/checkpoint-and-push",
            json=pod_spec_request.dict()
        )
        resp.raise_for_status()
        
        response_data = resp.json()
        logger.info(f"Checkpoint request sent successfully: {resp.status_code}")
        logger.info(f"Response: {response_data}")
        
        if response_data.get("success"):
            logger.info(f"Checkpoint and push completed successfully for pod {pod}")
            logger.info(f"Image tag: {response_data.get('image_tag', 'N/A')}")
        else:
            logger.error(f"Checkpoint operation failed: {response_data.get('message', 'Unknown error')}")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send checkpoint request to SnapApi: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during checkpoint request: {e}")
