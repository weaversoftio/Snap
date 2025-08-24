import json
from base64 import b64encode
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()

@router.post("/pods")
async def mutate_pods(request: Request):
    body = await request.json()
    uid = body["request"]["uid"]
    pod = body["request"]["object"]

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
