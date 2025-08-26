import json
import os
import yaml
import httpx
import asyncio
from base64 import b64encode
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/pods")
async def mutate_pods(request: Request):
    body = await request.json()
    uid = body["request"]["uid"]
    pod = body["request"]["object"]

    # Send pod data to SnapApi service
    cluster_name = os.getenv("CLUSTER_NAME", "Unknown")
    snapapi_url = os.getenv("SNAPAPI_URL", "http://snapapi-service:8000")
    
    try:
        # Send pod data as JSON to SnapApi
        webhook_data = {
            "cluster_name": cluster_name,
            "pod_data": pod
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{snapapi_url}/pod/webhook",
                json=webhook_data,
                timeout=10.0
            )
            
        if response.status_code == 200:
            logger.info(f"Successfully sent pod data to SnapApi for cluster: {cluster_name}")
        else:
            logger.error(f"Failed to send pod data to SnapApi. Status: {response.status_code}")
            
    except Exception as e:
        logger.error(f"Error sending pod data to SnapApi: {str(e)}")
        # Continue with webhook processing even if API call fails

    patches = []

    # Example: rewrite all container images
    for i, container in enumerate(pod["spec"].get("containers", [])):
        new = "docker.io/library/nginx:latest"
        patches.append({"op": "replace", "path": f"/spec/containers/{i}/image", "value": new})

    # Update label
    patches.append({
        "op": "replace",
        "path": "/metadata/labels/snap.weaversoft.io~1mutated",
        "value": "true"
    })

    return JSONResponse({
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "response": {
            "uid": uid,
            "allowed": True,
            "patchType": "JSONPatch",
            "patch": b64encode(json.dumps(patches).encode()).decode()
        }
    })
