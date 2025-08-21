import kopf
import logging
import requests
from kubernetes import client, config
from pydantic import BaseModel

# Track checkpointed pods
_ALREADY_CHECKPOINTED = set()

# Make sure client is usable inside cluster
config.load_incluster_config()
apps_api = client.AppsV1Api()

class PodCheckpointRequest(BaseModel):
    pod_name: str
    namespace: str
    node_name: str
    container_name: str
    kube_api_address: str


@kopf.on.event(
    'pods',
    labels={
        'snap.weaversoft.io/snap': 'true',
        'snap.weaversoft.io/mutated': 'false',
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

    logger.info(
        f"Now we should checkpoint\n"
        f"  Event:      {evt_type}\n"
        f"  Namespace:  {ns}\n"
        f"  Deployment: {deployment_name}\n"
        f"  Pod:        {name}\n"
        f"  Container:  {container_name}\n"
        f"  Node:       {node_name}"
    )

    # -----------------------------------------------------------------
    # Send checkpoint request to snap-back
    #
    # NOTE: This request will internally engage the kubelet endpoint at:
    #   {kube_api_address}/api/v1/nodes/{node_name}/proxy/checkpoint/{namespace}/{pod_name}/{container_name}
    # -----------------------------------------------------------------
    # try:
    #     req = PodCheckpointRequest(
    #         pod_name=name,
    #         namespace=ns,
    #         node_name=node_name,
    #         container_name=container_name,
    #         kube_api_address="https://<cluster_kube_api:port>",
    #     )
    #     resp = requests.post(
    #         "http://<snap-back-api>/kubelet/checkpoint",
    #         json=req.dict(),
    #         timeout=5,
    #     )
    #     resp.raise_for_status()
    #     logger.info(f"Checkpoint request sent successfully: {resp.status_code}")
    # except Exception as e:
    #     logger.error(f"Failed to send checkpoint request: {e}")