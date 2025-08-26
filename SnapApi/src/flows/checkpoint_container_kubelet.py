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

        # Handle different API address formats
        if kube_api_address.startswith('kubernetes.default.svc'):
            # Internal cluster access - ensure proper protocol and port
            kube_api_address = f"https://kubernetes.default.svc:443"
        elif not kube_api_address.startswith('http'):
            # External access - ensure https protocol
            kube_api_address = f"https://{kube_api_address}"

        # Construct the checkpoint endpoint
        kube_api_checkpoint_url = (
            f"{kube_api_address}/api/v1/nodes/{node_name}/proxy/checkpoint/{namespace}/{pod_name}/{container_name}"
        )
        print(f"Kube API URL: {kube_api_checkpoint_url}")

        checkpoint_cmd = [
            "curl", "-k", "-X", "POST",
            "--header", f"Authorization: Bearer {token}",
            kube_api_checkpoint_url
        ]
        print(f"Checkpoint command: {checkpoint_cmd}")
        await send_progress(username, {"progress": 30, "task_name": "Create Checkpoint", "message": f"Running command: \n{checkpoint_cmd}"})
        output = await run(checkpoint_cmd)
        stdout = output.stdout.strip()
        stderr = output.stderr.strip()

        # Log outputs
        print(f"STDOUT: {stdout}")
        print(f"STDERR: {stderr}")

        await send_progress(username, {
            "type": "progress",
            "name": "Checkpoint Output",
            "message": f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        })

        # Try to parse JSON
        try:
            checkpoint_data = json.loads(stdout)
            # handle normally if JSON
        except json.JSONDecodeError:
            # handle as plain error message
            error_message = f"Checkpoint failed:\n{stdout}"
            await send_progress(username, {
                "type": "progress",
                "name": "Create Checkpoint",
                "message": error_message
            })
            return PodCheckpointResponse(success=False, message=error_message)



        # Parse the JSON response to get the checkpoint file path

        try:
            checkpoint_data = json.loads(output.stdout)
            if checkpoint_data.get("items") and len(checkpoint_data["items"]) > 0:
                checkpoint_file_path = checkpoint_data["items"][0]
            else:
                await send_progress(username, {"progress": "failed", "task_name": "Create Checkpoint", "message": f"Error: No checkpoint file path found in response"})
                raise RuntimeError("No checkpoint file path found in response")
        except json.JSONDecodeError:
            await send_progress(username, {"progress": "failed", "task_name": "Create Checkpoint", "message": f"Error: Failed to parse checkpoint response as JSON"})
            raise RuntimeError("Failed to parse checkpoint response as JSON")
        
        # Upload the checkpoint file from the node
        checkpoint_filename = os.path.basename(checkpoint_file_path)
        debug_command = [
            "oc", "debug", f"node/{node_name}", "--",
            "chroot", "/host", "curl", "-X", "POST",
            f"{SNAP_API_URL}/checkpoint/upload/{pod_name}?filename={checkpoint_filename}",
            "-H", "accept: application/json",
            "-H", "Content-Type: multipart/form-data",
            "-F", f"file=@{checkpoint_file_path}"
        ]
        try:
            await send_progress(username, {"progress": 45, "task_name": "Create Checkpoint", "message": f"Running command: \n{debug_command}"})
            print(f"Executing debug command: {debug_command}")
            debug_output = await run(debug_command)
            print(f"Debug command stdout: {debug_output.stdout}")
            print(f"Debug command stderr: {debug_output.stderr}")
            await send_progress(username, {"progress": 60, "task_name": "Create Checkpoint", "message": f"Debug command stdout: {debug_output.stdout}"})
            await send_progress(username, {"progress": 75, "task_name": "Create Checkpoint", "message": f"Debug command stderr: {debug_output.stderr}"})
            
            if debug_output.returncode != 0:
                error_msg = f"Upload failed with return code {debug_output.returncode}. stderr: {debug_output.stderr}"
                print(error_msg)
                await send_progress(username, {"progress": "failed", "task_name": "Create Checkpoint", "message": f"Error: {error_msg}"})
                return PodCheckpointResponse(success=False, message=error_msg)
        except Exception as e:
            error_msg = f"Failed to upload checkpoint file: {str(e)}"
            print(error_msg)
            await send_progress(username, {"progress": "failed", "task_name": "Create Checkpoint", "message": f"Error: {error_msg}"})
            return PodCheckpointResponse(success=False, message=error_msg)

        await send_progress(username, {"progress": 100, "task_name": "Create Checkpoint", "message": f"All containers checkpointed successfully for pod: {pod_name}"})
        return PodCheckpointResponse(
            success=True,
            message=f"All containers checkpointed successfully for pod: {pod_name}",
            checkpoint_path=checkpoint_file_path,
            pod_name=pod_name,  # Include pod_name in response
            container_ids=container_name  # Include container_ids in response
        )

    except RuntimeError as e:
        print(e)
        await send_progress(username, {"progress": "failed", "task_name": "Create Checkpoint", "message": f"Error: {str(e)}"})
        return PodCheckpointResponse(success=False, message=str(e))
