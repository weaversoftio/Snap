import kopf
import logging
from datetime import datetime, timezone

# In-memory dedupe: remember which Pod UIDs we've already checkpointed.
# (Clears naturally when the operator restarts; good enough for ephemeral pods.)
_ALREADY_CHECKPOINTED = set()


@kopf.on.event('pods', labels={'snap.weaversoft.io/checkpoint-me': 'true'})
async def on_pod_event(event, body, logger, **kwargs):
    evt_type = (event or {}).get("type") or "UNKNOWN"

    metadata = body.get("metadata", {}) or {}
    status   = body.get("status", {}) or {}
    spec     = body.get("spec", {}) or {}

    ns    = metadata.get("namespace", "-")
    name  = metadata.get("name", "-")
    uid   = metadata.get("uid")

    # --- ignore deletions & terminating pods entirely ---
    if evt_type == "DELETED" or metadata.get("deletionTimestamp"):
        return

    # Ignore pods that already carry repo & fallback annotations
    annotations = metadata.get("annotations", {}) or {}
    if "snap.weaversoft.io/repo" in annotations and "snap.weaversoft.io/fallback" in annotations:
        logger.info(
            f"Annotations Detected!!, I'm not going to checkpoint this...\n"
            f"  Event:      {evt_type}\n"
            f"  Namespace:  {ns}\n"
            f"  Deployment: -\n"
            f"  Pod:        {name}\n"
            f"  Container:  {(spec.get('containers') or [{}])[0].get('name', '-')}"
        )
        return

    # Must be Running
    if status.get("phase") != "Running":
        return

    # Must report Ready=True
    conds = status.get("conditions", []) or []
    is_ready = any(c.get("type") == "Ready" and c.get("status") == "True" for c in conds)
    if not is_ready:
        return

    # At least one container started & in "running" state
    started = False
    for cs in status.get("containerStatuses", []) or []:
        state = cs.get("state", {}) or {}
        if "running" in state and cs.get("started"):
            started = True
            break
    if not started:
        return

    # --- reduce duplicates: fire only once per Pod UID after it becomes Ready ---
    if uid in _ALREADY_CHECKPOINTED:
        return
    _ALREADY_CHECKPOINTED.add(uid)

    # Best-effort container name (first container)
    container_name = "-"
    containers = spec.get("containers") or []
    if containers:
        container_name = containers[0].get("name", "-")

    # Print the message (with event type first, as you asked)
    logger.info(
        f"Now we should checkpoint\n"
        f"  Event:      {evt_type}\n"
        f"  Namespace:  {ns}\n"
        f"  Deployment: -\n"
        f"  Pod:        {name}\n"
        f"  Container:  {container_name}"
    )