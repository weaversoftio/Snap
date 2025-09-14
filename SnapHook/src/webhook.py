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
    cluster_name = os.getenv("CLUSTER_NAME", "Unknown").lower()
    snapapi_url = os.getenv("SNAPAPI_URL", "Unknown")
    
    # Debug logging
    print(f"SnapHook: Cluster name: {cluster_name}")
    print(f"SnapHook: SnapApi URL: {snapapi_url}")
    
    # Validate URL has protocol
    if not snapapi_url.startswith(('http://', 'https://')):
        print(f"SnapHook: URL missing protocol, adding http://")
        snapapi_url = f"http://{snapapi_url}"
        print(f"SnapHook: Fixed URL: {snapapi_url}")
    
    patches = []
    should_patch_image = False
    generated_image_tag = None
    
    try:
        # Send pod data as JSON to SnapApi
        webhook_data = {
            "cluster_name": cluster_name,
            "pod_data": pod
        }
        
        print(f"SnapHook: Sending request to: {snapapi_url}/pod/webhook")
        print(f"SnapHook: Request data: {webhook_data}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{snapapi_url}/pod/webhook",
                json=webhook_data,
                timeout=10.0
            )
            
        if response.status_code == 200:
            api_response = response.json()
            print(f"Successfully sent pod data to SnapApi for cluster: {cluster_name}")
            print(f"SnapApi response: {api_response}")
            
            # Check if image exists in registry
            if api_response.get("exist") == "True":
                should_patch_image = True
                generated_image_tag = api_response.get("generated_image_tag")
                print(f"Image exists in registry, will patch with: {generated_image_tag}")
            else:
                print("Image does not exist in registry, skipping image patch")
                
        else:
            logger.error(f"Failed to send pod data to SnapApi. Status: {response.status_code}")
            print(f"SnapHook: Response content: {response.text}")
            
    except Exception as e:
        logger.error(f"Error sending pod data to SnapApi: {str(e)}")
        print(f"SnapHook: Exception details: {str(e)}")
        # Continue with webhook processing even if API call fails

    # Only patch container images if the generated image exists in the registry
    if should_patch_image and generated_image_tag:
        for i, container in enumerate(pod["spec"].get("containers", [])):
            print(f"Patching container {i} image to: {generated_image_tag}")
            patches.append({"op": "replace", "path": f"/spec/containers/{i}/image", "value": generated_image_tag})
    else:
        print("Skipping image patching - image does not exist in registry or API call failed")

    # Only add the mutation label if we actually patched the image
    if should_patch_image and generated_image_tag:
        patches.append({
            "op": "replace",
            "path": "/metadata/labels/snap.weaversoft.io~1mutated",
            "value": "true"
        })
        print("Added mutated=true label because image was patched")
    else:
        print("Skipping mutated=true label - no image patching occurred")

    # Build response conditionally based on whether patches exist
    response_data = {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "response": {
            "uid": uid,
            "allowed": True
        }
    }
    
    # Only include patch fields if we have patches to apply
    if patches:
        response_data["response"]["patchType"] = "JSONPatch"
        response_data["response"]["patch"] = b64encode(json.dumps(patches).encode()).decode()
    
    return JSONResponse(response_data)
