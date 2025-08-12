#!/usr/bin/env python3
"""
Simple Kubernetes Operator for Snap
Watches for pods with specific snap annotations and logs container information.
"""

import kopf
import logging
from kubernetes import client, config
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()

def has_snap_annotations(annotations: Dict[str, str]) -> bool:
    if not annotations:
        return False
    return 'snap/containers' in annotations or 'snap/info' in annotations

def on_pod_with_snap_annotations(pod: Dict[str, Any]):
    metadata = pod.get('metadata', {})
    namespace = metadata.get('namespace', 'unknown')
    pod_name = metadata.get('name', 'unknown')

    spec = pod.get('spec', {})
    containers = spec.get('containers', [])
    if not containers:
        return

    # Print each container on its own line: namespace-pod-container
    for container in containers:
        container_name = container.get('name', 'unknown')
        logger.info(f"{namespace}-{pod_name}-{container_name}")

@kopf.on.event('', 'v1', 'pods')
def on_pod_event(event, **_):
    try:
        pod = event['object']
        annotations = pod.get('metadata', {}).get('annotations', {})
        if has_snap_annotations(annotations):
            on_pod_with_snap_annotations(pod)
    except Exception as exc:
        logger.error(f"Error processing pod event: {exc}")

@kopf.on.startup()
def on_startup(**_):
    logger.info("Snap Operator started")

@kopf.on.cleanup()
def on_cleanup(**_):
    logger.info("Snap Operator stopping")
