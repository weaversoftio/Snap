"""
Integrated SnapWatcher operator functionality.
This module contains the Kopf operator that watches for pods and triggers checkpointing.
"""

import os
import logging
import kopf
from kubernetes import client, config
from classes.apirequests import PodSpecCheckpointRequest
from flows.checkpoint_and_push_combined import checkpoint_and_push_combined_from_pod_spec

logger = logging.getLogger("automation_api")

# Setup Kubernetes client for operator functionality based on WatcherMode
watcher_mode = os.getenv("WATCHER_MODE", "off").lower()

if watcher_mode == "off":
    print("SnapWatcher: WatcherMode is 'off' - operator will not start")
    # Don't load any Kubernetes config
elif watcher_mode == "cluster":
    try:
        # Load in-cluster config
        config.load_incluster_config()
        print("SnapWatcher: Loaded in-cluster Kubernetes configuration")
    except config.ConfigException:
        print("SnapWatcher: Could not load in-cluster Kubernetes configuration")
elif watcher_mode == "compose":
    try:
        # Load kubeconfig for external cluster access using KUBECONFIG env
        kubeconfig_path = os.getenv("KUBECONFIG", "/app/.kube/config")
        config.load_kube_config(config_file=kubeconfig_path)
        print(f"SnapWatcher: Loaded kubeconfig from {kubeconfig_path}")
    except config.ConfigException:
        print("SnapWatcher: Could not load kubeconfig")
else:
    print(f"SnapWatcher: Invalid WatcherMode '{watcher_mode}' - valid options are 'off', 'cluster', or 'compose'")

# Define the pod event handler (integrated SnapWatcher functionality)
@kopf.on.event(
    'pods',
    labels={
        'snap.weaversoft.io/snap': kopf.PRESENT,   
        'snap.weaversoft.io/mutated': kopf.ABSENT 
    },
)
async def on_pod_event(event, body, logger, **kwargs):
    """Integrated SnapWatcher: Handle pod events for checkpointing"""
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

    logger.info(
        f"SnapWatcher: Processing checkpoint request\n"
        f"  Event:      {evt_type}\n"
        f"  Namespace:  {ns}\n"
        f"  Pod:        {pod}\n"
        f"  Container:  {container_name}\n"
        f"  Node:       {node_name}"
    )

    # -----------------------------------------------------------------
    # Directly call the checkpoint function instead of HTTP request
    # -----------------------------------------------------------------
    try:
        # Prepare the complete pod specification for the request
        pod_spec_request = PodSpecCheckpointRequest(pod_spec=body)
        
        # Use a default username for operator-triggered checkpoints
        username = "snapwatcher-operator"
        
        # Get cluster name from environment variable
        cluster = os.getenv("WATCHER_CLUSTER_NAME", "crc")
        
        logger.info(f"SnapWatcher: Calling checkpoint function directly for pod {pod} in cluster {cluster}")
        
        # Call the checkpoint function directly
        result = await checkpoint_and_push_combined_from_pod_spec(pod_spec_request, cluster, username)
        
        print(f"SnapWatcher: Checkpoint operation completed: {result.get('success', False)}")
        
        if result.get("success"):
            logger.info(f"SnapWatcher: Checkpoint and push completed successfully for pod {pod}")
            logger.info(f"SnapWatcher: Image tag: {result.get('image_tag', 'N/A')}")
        else:
            logger.error(f"SnapWatcher: Checkpoint operation failed: {result.get('message', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"SnapWatcher: Unexpected error during checkpoint operation: {e}")
