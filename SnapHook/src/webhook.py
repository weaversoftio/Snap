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
    snapapi_url = os.getenv("SNAPAPI_URL", "http://snapapi:8000")
    
    patches = []
    should_patch_image = False
    generated_image_tag = None
    
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
            api_response = response.json()
            logger.info(f"Successfully sent pod data to SnapApi for cluster: {cluster_name}")
            logger.info(f"SnapApi response: {api_response}")
            
            # Check if image exists in registry
            if api_response.get("exist") == "True":
                should_patch_image = True
                generated_image_tag = api_response.get("generated_image_tag")
                logger.info(f"Image exists in registry, will patch with: {generated_image_tag}")
            else:
                logger.info("Image does not exist in registry, skipping image patch")
                
        else:
            logger.error(f"Failed to send pod data to SnapApi. Status: {response.status_code}")
            
    except Exception as e:
        logger.error(f"Error sending pod data to SnapApi: {str(e)}")
        # Continue with webhook processing even if API call fails

    # Only patch container images if the generated image exists in the registry
    if should_patch_image and generated_image_tag:
        for i, container in enumerate(pod["spec"].get("containers", [])):
            logger.info(f"Patching container {i} image to: {generated_image_tag}")
            patches.append({"op": "replace", "path": f"/spec/containers/{i}/image", "value": generated_image_tag})
    else:
        logger.info("Skipping image patching - image does not exist in registry or API call failed")

    # Always update the mutation label to indicate the webhook processed this pod
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
