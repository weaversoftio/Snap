import os
import subprocess
import json
from classes.apirequests import PodCheckpointRequest, PodCheckpointResponse
from flows.proccess_utils import run

def load_cluster_config(cluster_name: str) -> dict:
    """
    Load cluster configuration from config/clusters/{cluster_name}.json
    
    Args:
        cluster_name: The cluster name to load configuration for
        
    Returns:
        Dictionary containing kube_api_url and token
        
    Raises:
        ValueError: If cluster configuration is not found
    """
    cluster_path = f"config/clusters/{cluster_name}.json"
    if not os.path.exists(cluster_path):
        raise ValueError(f"Cluster configuration not found: {cluster_name}")
    
    with open(cluster_path, 'r') as f:
        cluster_data = json.load(f)
    
    cluster_details = cluster_data["cluster_config_details"]
    return {
        "kube_api_url": cluster_details["kube_api_url"],
        "token": cluster_details["token"]
    }
SNAP_API_URL = os.getenv("SNAP_API_URL", "http://snapapi.apps-crc.testing")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
checkpoint_path = os.path.join(BASE_DIR, 'checkpoints')
os.makedirs(checkpoint_path, exist_ok=True)

async def create_directory(checkpoint_path: str, directory_name: str) -> str:
    directory_path = f"{checkpoint_path}/{directory_name}"
    try:
        await run(["mkdir", "-p", directory_path])
        print(f"SnapAPI: Directory {directory_path} created successfully.")
        return directory_path
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to create directory {directory_path}: {e}")

async def checkpoint_container_kubelet(request: PodCheckpointRequest) -> PodCheckpointResponse:
    try:
        pod_name = request.pod_name
        namespace = request.namespace
        node_name = request.node_name
        container_name = request.container_name
        cluster_name = request.cluster_name

        # Load cluster configuration from config/clusters
        cluster_config = load_cluster_config(cluster_name)
        kube_api_address = cluster_config["kube_api_url"]
        token = cluster_config["token"]
        
        print(f"SnapAPI: Using cluster config: {cluster_name}")
        print(f"SnapAPI: Token: {token[:20]}...")  # Only show first 20 chars for security

        # Handle different API address formats
        if kube_api_address.startswith('kubernetes.default.svc'):
            kube_api_address = "https://kubernetes.default.svc:443"
        elif not kube_api_address.startswith("http"):
            kube_api_address = f"https://{kube_api_address}"

        # Use Kubernetes API URL format for checkpoint
        kube_api_checkpoint_url = f"{kube_api_address}/api/v1/nodes/{node_name}/proxy/checkpoint/{namespace}/{pod_name}/{container_name}"
        print(f"SnapAPI: Kube API URL: {kube_api_checkpoint_url}")
        
        # Build curl command with SSL verification control
        verify_ssl = os.getenv('KUBE_VERIFY_SSL', 'false').lower() == 'true'
        checkpoint_cmd = [
            "curl", "-X", "POST",
            "--header", f"Authorization: Bearer {token}",
            kube_api_checkpoint_url
        ]
        
        if not verify_ssl:
            checkpoint_cmd.insert(1, "-k")  # Add -k flag for insecure connections
        print(f"SnapAPI: Checkpoint command: {checkpoint_cmd}")
        output = await run(checkpoint_cmd)
        print(f"SnapAPI: Output: {output}")

        # Parse the JSON response to get the checkpoint file path
        try:
            checkpoint_data = json.loads(output.stdout)
            if checkpoint_data.get("items") and len(checkpoint_data["items"]) > 0:
                checkpoint_file_path = checkpoint_data["items"][0]
            else:
                raise RuntimeError("No checkpoint file path found in response")
        except json.JSONDecodeError:
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
            print(f"SnapAPI: Executing debug command: {debug_command}")
            debug_output = await run(debug_command)
            print(f"SnapAPI: Debug command stdout: {debug_output.stdout}")
            print(f"SnapAPI: Debug command stderr: {debug_output.stderr}")
            if debug_output.returncode != 0:
                error_msg = f"Upload failed with return code {debug_output.returncode}. stderr: {debug_output.stderr}"
                print(f"SnapAPI: {error_msg}")
                return PodCheckpointResponse(success=False, message=error_msg)
        except Exception as e:
            error_msg = f"Failed to upload checkpoint file: {str(e)}"
            print(f"SnapAPI: {error_msg}")
            return PodCheckpointResponse(success=False, message=error_msg)

        return PodCheckpointResponse(
            success=True,
            message=f"All containers checkpointed successfully for pod: {pod_name}",
            checkpoint_path=checkpoint_file_path,
            pod_name=pod_name,  # Include pod_name in response
            container_ids=container_name  # Include container_ids in response
        )

    except RuntimeError as e:
        print(f"SnapAPI: {e}")
        return PodCheckpointResponse(success=False, message=str(e))
