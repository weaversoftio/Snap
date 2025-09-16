import os
import subprocess
import json
from classes.apirequests import PodCheckpointRequest, PodCheckpointResponse
from flows.proccess_utils import run
from routes.websocket import send_progress

SNAP_API_URL = os.getenv("SNAP_API_URL", "http://snapapi.apps-crc.testing")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
checkpoint_path = os.path.join(BASE_DIR, 'checkpoints')
os.makedirs(checkpoint_path, exist_ok=True)

async def create_directory(checkpoint_path: str, directory_name: str) -> str:
    directory_path = f"{checkpoint_path}/{directory_name}"
    try:
        await run(["mkdir", "-p", directory_path])
        print(f"Directory {directory_path} created successfully.")
        return directory_path
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to create directory {directory_path}: {e}")

async def checkpoint_container_kubelet(request: PodCheckpointRequest, username: str) -> PodCheckpointResponse:
    try:
        pod_name = request.pod_name
        namespace = request.namespace
        node_name = request.node_name
        container_name = request.container_name
        kube_api_address = request.kube_api_address

        await send_progress(username, {"progress": 15, "task_name": "Create Checkpoint", "message": f"Creating Checkpoint initiated, name: {pod_name}"})

        # Get service account token - handle both in-cluster and external access
        try:
            # Try to read the service account token from the mounted volume (in-cluster)
            with open('/var/run/secrets/kubernetes.io/serviceaccount/token', 'r') as token_file:
                token = token_file.read().strip()
                print("Using in-cluster service account token")
        except FileNotFoundError:
            # Fallback to oc command for external access
            token = (await run(["oc", "whoami", "-t"])).stdout.strip()
            print("Using oc whoami token")
        
        print(f"Token: {token[:20]}...")  # Only show first 20 chars for security

        # Handle different API address formats - match checkpoint_and_push.py logic
        if kube_api_address.startswith('kubernetes.default.svc'):
            kube_api_address = "https://kubernetes.default.svc:443"
        elif not kube_api_address.startswith("http"):
            kube_api_address = f"https://{kube_api_address}"

        # Construct the checkpoint endpoint
        kube_api_checkpoint_url = (
            f"{kube_api_address}/api/v1/nodes/{node_name}/proxy/checkpoint/{namespace}/{pod_name}/{container_name}"
        )
        print(f"Kube API URL: {kube_api_checkpoint_url}")

        # Build curl command with Bearer token - match checkpoint_and_push.py
        checkpoint_cmd = [
            "curl", "-k", "-X", "POST",
            "--header", f"Authorization: Bearer {token}",
            kube_api_checkpoint_url
        ]

        await send_progress(username, {"progress": 30, "task_name": "Create Checkpoint", "message": f"Creating checkpoint for {pod_name}/{container_name}"})
        
        print(f"SnapAPI: Creating checkpoint: {pod_name}/{container_name}")
        print(f"SnapAPI: Checkpoint API URL: {kube_api_checkpoint_url}")
        
        output = await run(checkpoint_cmd)
        stdout = (output.stdout or "").strip()
        stderr = (output.stderr or "").strip()
        
        print(f"SnapAPI: Checkpoint API response: {stdout[:200]}...")
        if stderr:
            print(f"SnapAPI: Checkpoint API stderr: {stderr[:200]}...")

        # Parse kubelet response - match checkpoint_and_push.py logic
        try:
            checkpoint_data = json.loads(stdout)
        except json.JSONDecodeError:
            error_msg = f"Checkpoint API did not return JSON.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
            await send_progress(username, {
                "progress": "failed", 
                "task_name": "Create Checkpoint", 
                "message": f"Checkpoint creation failed: Invalid JSON response"
            })
            return PodCheckpointResponse(success=False, message=error_msg)

        items = checkpoint_data.get("items") or []
        if not items:
            error_msg = f"No checkpoint file path found in API response.\n{stdout}"
            await send_progress(username, {
                "progress": "failed", 
                "task_name": "Create Checkpoint", 
                "message": f"Checkpoint creation failed: No checkpoint file path in response"
            })
            return PodCheckpointResponse(success=False, message=error_msg)

        checkpoint_file_path = items[0]
        checkpoint_filename = os.path.basename(checkpoint_file_path)
        
        await send_progress(username, {
            "progress": 40, 
            "task_name": "Create Checkpoint", 
            "message": f"Checkpoint created successfully at {checkpoint_file_path}"
        })
        
        print(f"SnapAPI: Checkpoint created at: {checkpoint_file_path}")
        
        # Upload the checkpoint file from the node - match checkpoint_and_push.py logic
        debug_command = [
            "oc", "debug", f"node/{node_name}", "--",
            "chroot", "/host", "curl", "-X", "POST",
            f"{SNAP_API_URL}/checkpoint/upload/{pod_name}?filename={checkpoint_filename}",
            "-H", "accept: application/json",
            "-H", "Content-Type: multipart/form-data",
            "-F", f"file=@{checkpoint_file_path}"
        ]
        try:
            await send_progress(username, {"progress": 50, "task_name": "Create Checkpoint", "message": f"Uploading checkpoint file from node"})
            
            print(f"SnapAPI: Uploading checkpoint from node: {checkpoint_file_path}")
            print(f"SnapAPI: Curl Command: {debug_command}")
            print(f"SnapAPI: Upload URL: {SNAP_API_URL}/checkpoint/upload/{pod_name}?filename={checkpoint_filename}")
            
            # Call debug command
            print(f"SnapAPI: Executing debug command: {debug_command}")
            debug_output = await run(debug_command)
            
            if debug_output.stdout:
                print(f"SnapAPI: Upload result: {debug_output.stdout[:200]}...")
            if debug_output.stderr:
                print(f"SnapAPI: Upload stderr: {debug_output.stderr[:200]}...")
            
            if debug_output.returncode != 0:
                error_msg = f"Upload failed: {debug_output.stderr[:100]}..."
                await send_progress(username, {
                    "progress": "failed", 
                    "task_name": "Create Checkpoint", 
                    "message": f"Upload failed: {debug_output.stderr[:100]}..."
                })
                print(f"SnapAPI: {error_msg}")
                return PodCheckpointResponse(success=False, message=error_msg)
        except Exception as e:
            error_msg = f"Upload error: {str(e)}"
            await send_progress(username, {
                "progress": "failed", 
                "task_name": "Create Checkpoint", 
                "message": f"Upload error: {str(e)}"
            })
            print(f"SnapAPI: {error_msg}")
            return PodCheckpointResponse(success=False, message=error_msg)

        await send_progress(username, {"progress": 100, "task_name": "Create Checkpoint", "message": f"All containers checkpointed successfully for pod: {pod_name}"})
        return PodCheckpointResponse(
            success=True,
            message=f"All containers checkpointed successfully for pod: {pod_name}",
            checkpoint_path=checkpoint_file_path,
            pod_name=pod_name,  # Include pod_name in response
            container_ids=container_name  # Include container_ids in response
        )

    except Exception as e:
        err = f"Checkpoint operation failed: {e}"
        await send_progress(username, {
            "progress": "failed", 
            "task_name": "Create Checkpoint", 
            "message": f"Operation failed: {str(e)}"
        })
        return PodCheckpointResponse(success=False, message=err)
