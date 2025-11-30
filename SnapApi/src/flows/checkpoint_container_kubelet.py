import os
import subprocess
import json
from classes.apirequests import PodCheckpointRequest, PodCheckpointResponse
from flows.proccess_utils import run
from routes.websocket import send_progress
from flows.helpers import extract_app_name_from_pod, get_snap_config_from_cluster_cache_api, resolve_digest_with_skopeo

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

async def fetch_pod_info_from_k8s_api(pod_name: str, namespace: str, cluster_config: dict) -> dict:
    """
    Fetch pod information from Kubernetes API to extract metadata for JSON creation.
    
    Args:
        pod_name: Name of the pod
        namespace: Kubernetes namespace
        cluster_config: Cluster configuration containing kube_api_url and token
        
    Returns:
        Dictionary containing extracted pod metadata
    """
    try:
        kube_api_address = cluster_config["kube_api_url"]
        token = cluster_config["token"]
        
        # Handle different API address formats
        if kube_api_address.startswith('kubernetes.default.svc'):
            kube_api_address = "https://kubernetes.default.svc:443"
        elif not kube_api_address.startswith("http"):
            kube_api_address = f"https://{kube_api_address}"
        
        # Construct the pod API endpoint
        pod_api_url = f"{kube_api_address}/api/v1/namespaces/{namespace}/pods/{pod_name}"
        
        # Build curl command to fetch pod information
        verify_ssl = os.getenv('KUBE_VERIFY_SSL', 'false').lower() == 'true'
        curl_cmd = [
            "curl", "-X", "GET",
            "--header", f"Authorization: Bearer {token}",
            "--header", "Accept: application/json",
            pod_api_url
        ]
        
        if not verify_ssl:
            curl_cmd.insert(1, "-k")  # Add -k flag for insecure connections
        
        print(f"SnapAPI: Fetching pod info from: {pod_api_url}")
        output = await run(curl_cmd)
        
        if output.returncode != 0:
            print(f"SnapAPI: Failed to fetch pod info: {output.stderr}")
            return {}
        
        # Debug: Print first 200 chars of response
        stdout_preview = output.stdout[:200] if output.stdout else "No stdout"
        print(f"SnapAPI: Pod API response preview: {stdout_preview}")
        
        try:
            pod_data = json.loads(output.stdout)
        except json.JSONDecodeError as e:
            print(f"SnapAPI: Failed to parse pod API response as JSON: {e}")
            print(f"SnapAPI: Full response: {output.stdout}")
            return {}
        
        # Extract required information
        metadata = pod_data.get("metadata", {})
        spec = pod_data.get("spec", {})
        labels = metadata.get("labels", {})
        containers = spec.get("containers", [])
        
        print(f"SnapAPI: Extracted labels: {labels}")
        print(f"SnapAPI: Found {len(containers)} containers")
        
        # Extract pod template hash
        pod_template_hash = labels.get("pod-template-hash", "no-hash")
        print(f"SnapAPI: Pod template hash: {pod_template_hash}")
        
        # Extract app name
        app = extract_app_name_from_pod(pod_name, labels)
        print(f"SnapAPI: Extracted app name: {app}")
        
        # Extract container image (use first container or find by container name)
        container_image = ""
        if containers:
            container_image = containers[0].get("image", "")
            print(f"SnapAPI: Container image: {container_image}")
        
        # Extract digest from container image using skopeo (like other files)
        orig_image_short_digest = ""
        if container_image:
            try:
                print(f"SnapAPI: Resolving digest for image: {container_image}")
                digest = await resolve_digest_with_skopeo(container_image)
                if digest and digest != "unknown":
                    # Extract short digest (first 12 characters after sha256:)
                    if digest.startswith("sha256:"):
                        orig_image_short_digest = digest[7:19]  # Remove "sha256:" and take first 12 chars
                    else:
                        orig_image_short_digest = digest[:12]
                    print(f"SnapAPI: Resolved digest: {digest} -> short: {orig_image_short_digest}")
                else:
                    print(f"SnapAPI: Could not resolve digest for image: {container_image}")
            except Exception as e:
                print(f"SnapAPI: Error resolving digest with skopeo: {e}")
                orig_image_short_digest = ""
        
        return {
            "pod_template_hash": pod_template_hash,
            "app": app,
            "container_image": container_image,
            "orig_image_short_digest": orig_image_short_digest,
            "labels": labels
        }
        
    except Exception as e:
        print(f"SnapAPI: Error fetching pod info: {e}")
        return {}

async def get_pod_template_hash_with_oc(pod_name: str, namespace: str) -> str:
    """
    Get pod template hash using oc command as an alternative to labels.
    Tries multiple approaches to find the template hash.
    
    Args:
        pod_name: Name of the pod
        namespace: Kubernetes namespace
        
    Returns:
        Pod template hash string or "no-hash" if not found
    """
    try:
        # Approach 1: Try to get from pod labels directly
        oc_cmd = [
            "oc", "get", "pod", pod_name, 
            "-n", namespace, 
            "-o", "jsonpath={.metadata.labels.pod-template-hash}"
        ]
        
        print(f"SnapAPI: Getting pod template hash with oc (approach 1): {' '.join(oc_cmd)}")
        output = await run(oc_cmd)
        
        if output.returncode == 0 and output.stdout and output.stdout.strip():
            template_hash = output.stdout.strip()
            print(f"SnapAPI: Pod template hash from pod labels: {template_hash}")
            return template_hash
        
        # Approach 2: Try to get from ownerReferences (deployment/replicaset)
        oc_cmd2 = [
            "oc", "get", "pod", pod_name, 
            "-n", namespace, 
            "-o", "jsonpath={.metadata.ownerReferences[0].name}"
        ]
        
        print(f"SnapAPI: Getting owner reference with oc (approach 2): {' '.join(oc_cmd2)}")
        output2 = await run(oc_cmd2)
        
        if output2.returncode == 0 and output2.stdout and output2.stdout.strip():
            owner_name = output2.stdout.strip()
            print(f"SnapAPI: Found owner reference: {owner_name}")
            
            # Try to get template hash from replicaset
            oc_cmd3 = [
                "oc", "get", "replicaset", owner_name, 
                "-n", namespace, 
                "-o", "jsonpath={.metadata.labels.pod-template-hash}"
            ]
            
            print(f"SnapAPI: Getting template hash from replicaset: {' '.join(oc_cmd3)}")
            output3 = await run(oc_cmd3)
            
            if output3.returncode == 0 and output3.stdout and output3.stdout.strip():
                template_hash = output3.stdout.strip()
                print(f"SnapAPI: Pod template hash from replicaset: {template_hash}")
                return template_hash
        
        # Approach 3: Try to get from deployment directly
        oc_cmd4 = [
            "oc", "get", "pod", pod_name, 
            "-n", namespace, 
            "-o", "jsonpath={.metadata.labels.app\\.kubernetes\\.io/name}"
        ]
        
        print(f"SnapAPI: Getting app name with oc (approach 3): {' '.join(oc_cmd4)}")
        output4 = await run(oc_cmd4)
        
        if output4.returncode == 0 and output4.stdout and output4.stdout.strip():
            app_name = output4.stdout.strip()
            print(f"SnapAPI: Found app name: {app_name}")
            
            # Try to get deployment and its template hash
            oc_cmd5 = [
                "oc", "get", "deployment", app_name, 
                "-n", namespace, 
                "-o", "jsonpath={.metadata.labels.pod-template-hash}"
            ]
            
            print(f"SnapAPI: Getting template hash from deployment: {' '.join(oc_cmd5)}")
            output5 = await run(oc_cmd5)
            
            if output5.returncode == 0 and output5.stdout and output5.stdout.strip():
                template_hash = output5.stdout.strip()
                print(f"SnapAPI: Pod template hash from deployment: {template_hash}")
                return template_hash
        
        # Approach 4: Try to extract from pod name (common pattern: app-hash-random)
        print(f"SnapAPI: Trying to extract hash from pod name: {pod_name}")
        import re
        # Look for pattern like: app-1234567890-abcde or app-1234567890
        hash_match = re.search(r'-([a-f0-9]{8,10})(-[a-f0-9]{5})?$', pod_name)
        if hash_match:
            extracted_hash = hash_match.group(1)
            print(f"SnapAPI: Extracted hash from pod name: {extracted_hash}")
            return extracted_hash
        
        # Approach 5: Try to get all labels and look for any hash-like pattern
        oc_cmd6 = [
            "oc", "get", "pod", pod_name, 
            "-n", namespace, 
            "-o", "jsonpath={.metadata.labels}"
        ]
        
        print(f"SnapAPI: Getting all pod labels (approach 5): {' '.join(oc_cmd6)}")
        output6 = await run(oc_cmd6)
        
        if output6.returncode == 0 and output6.stdout:
            labels_json = output6.stdout.strip()
            print(f"SnapAPI: All pod labels: {labels_json}")
            
            # Look for any hash-like values in labels
            hash_patterns = [
                r'"([a-f0-9]{8,10})"',  # 8-10 hex chars
                r'"([a-f0-9]{7})"',     # 7 hex chars
                r'"([a-f0-9]{9})"',     # 9 hex chars
            ]
            
            for pattern in hash_patterns:
                matches = re.findall(pattern, labels_json)
                if matches:
                    # Take the first match that looks like a hash
                    for match in matches:
                        if len(match) >= 7:  # Reasonable hash length
                            print(f"SnapAPI: Found hash-like value in labels: {match}")
                            return match
        
        # Approach 6: Generate a hash from pod name as last resort
        print(f"SnapAPI: Generating hash from pod name as last resort")
        import hashlib
        pod_hash = hashlib.md5(pod_name.encode()).hexdigest()[:8]
        print(f"SnapAPI: Generated hash from pod name: {pod_hash}")
        return pod_hash
            
    except Exception as e:
        print(f"SnapAPI: Error getting pod template hash with oc: {e}")
        return "no-hash"

async def checkpoint_container_kubelet(request: PodCheckpointRequest, username: str) -> PodCheckpointResponse:
    try:
        pod_name = request.pod_name
        namespace = request.namespace
        node_name = request.node_name
        container_name = request.container_name
        cluster_name = request.cluster_name

        await send_progress(username, {"progress": 15, "task_name": "Create Checkpoint", "message": f"Creating Checkpoint initiated, name: {pod_name}"})

        # Load cluster configuration from config/clusters
        cluster_config = load_cluster_config(cluster_name)
        kube_api_address = cluster_config["kube_api_url"]
        token = cluster_config["token"]
        
        print(f"SnapAPI: Using cluster config: {cluster_name}")
        print(f"SnapAPI: Token: {token[:20]}...")  # Only show first 20 chars for security

        # Handle different API address formats - match checkpoint_and_push.py logic
        if kube_api_address.startswith('kubernetes.default.svc'):
            kube_api_address = "https://kubernetes.default.svc:443"
        elif not kube_api_address.startswith("http"):
            kube_api_address = f"https://{kube_api_address}"

        # Construct the checkpoint endpoint
        kube_api_checkpoint_url = (
            f"{kube_api_address}/api/v1/nodes/{node_name}/proxy/checkpoint/{namespace}/{pod_name}/{container_name}"
        )
        print(f"SnapAPI: Kube API URL: {kube_api_checkpoint_url}")

        # Build curl command with Bearer token and SSL verification control
        verify_ssl = os.getenv('KUBE_VERIFY_SSL', 'false').lower() == 'true'
        checkpoint_cmd = [
            "curl", "-X", "POST",
            "--header", f"Authorization: Bearer {token}",
            kube_api_checkpoint_url
        ]
        
        if not verify_ssl:
            checkpoint_cmd.insert(1, "-k")  # Add -k flag for insecure connections

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
        
        # Create JSON metadata file locally (not on the node)
        try:
            await send_progress(username, {
                "progress": 45, 
                "task_name": "Create Checkpoint", 
                "message": f"Creating checkpoint metadata file"
            })
            
            # Fetch pod information from Kubernetes API
            pod_info = await fetch_pod_info_from_k8s_api(pod_name, namespace, cluster_config)
            
            # Get pod template hash using oc command
            pod_template_hash = await get_pod_template_hash_with_oc(pod_name, namespace)
            
            # Get cache registry and repo configuration
            try:
                snap_config = await get_snap_config_from_cluster_cache_api(cluster_name)
                cache_registry = snap_config["cache_registry"]
                cache_repo = snap_config["cache_repo"]
            except Exception as e:
                print(f"SnapAPI: Failed to load cluster cache config: {e}")
                # Fallback to environment variables
                cache_registry = os.getenv("snap_registry", "docker.io")
                cache_repo = os.getenv("snap_repo", "snap")
            
            # Extract pod information with fallbacks
            app = pod_info.get("app", pod_name)  # Use pod_name as fallback
            container_image = pod_info.get("container_image", "unknown")
            orig_image_short_digest = pod_info.get("orig_image_short_digest", "unknown")
            
            # Generate image tag using the extracted information
            image_tag = f"{cache_registry}/{cache_repo}/{cluster_name.lower()}-{namespace}-{app}:{orig_image_short_digest}-{pod_template_hash}"
            
            # Create JSON metadata locally in the SnapAPI pod
            local_checkpoint_path = os.path.join(checkpoint_path, pod_name)
            os.makedirs(local_checkpoint_path, exist_ok=True)
            
            # Create metadata dictionary
            metadata = {
                "checkpoint_info": {
                    "checkpoint_file_path": checkpoint_file_path,
                    "checkpoint_filename": checkpoint_filename,
                    "created_at": None,  # Could be added if timestamp is needed
                },
                "image_info": {
                    "image_tag": image_tag,
                    "original_image": container_image,
                    "original_image_digest": orig_image_short_digest,
                    "registry": cache_registry,
                    "repository": cache_repo,
                },
                "pod_info": {
                    "pod_name": pod_name,
                    "namespace": namespace,
                    "container_name": container_name,
                    "app": app,
                    "cluster": cluster_name,
                    "pod_template_hash": pod_template_hash,
                    "node_name": node_name,
                },
                "generation_info": {
                    "image_tag_format": f"{cache_registry}/{cache_repo}/{cluster_name.lower()}-{namespace}-{app}:{orig_image_short_digest}-{pod_template_hash}",
                    "cluster_normalized": cluster_name.lower(),
                }
            }
            
            # Generate JSON file path locally
            json_filename = os.path.splitext(checkpoint_filename)[0] + ".json"
            # Apply same normalization as TAR files to ensure consistent naming
            json_filename = json_filename.replace('-', '_').replace(':', '_').replace('+', '_')
            local_json_file_path = os.path.join(local_checkpoint_path, json_filename)
            
            # Validate metadata before writing
            print(f"SnapAPI: Metadata to write: {json.dumps(metadata, indent=2)}")
            
            # Write JSON file locally
            with open(local_json_file_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Verify the file was written correctly
            try:
                with open(local_json_file_path, 'r') as f:
                    verification_data = json.load(f)
                print(f"SnapAPI: JSON file verification successful. File size: {os.path.getsize(local_json_file_path)} bytes")
                print(f"SnapAPI: Checkpoint metadata JSON created locally at: {local_json_file_path}")
            except Exception as verify_error:
                print(f"SnapAPI: JSON file verification failed: {verify_error}")
                # Try to read raw content for debugging
                try:
                    with open(local_json_file_path, 'rb') as f:
                        raw_content = f.read(200)
                        print(f"SnapAPI: Raw file content preview: {raw_content}")
                except Exception as read_error:
                    print(f"SnapAPI: Could not read file for debugging: {read_error}")
            
        except Exception as e:
            print(f"SnapAPI: Warning - Failed to create checkpoint metadata JSON: {e}")
            # Don't fail the entire operation if JSON creation fails
            local_json_file_path = None
        
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
            # Sanitize command before printing
            from flows.proccess_utils import sanitize_command_for_logging
            _, sanitized_cmd_str = sanitize_command_for_logging(debug_command)
            print(f"SnapAPI: Curl Command: {sanitized_cmd_str}")
            print(f"SnapAPI: Upload URL: {SNAP_API_URL}/checkpoint/upload/{pod_name}?filename={checkpoint_filename}")
            
            # Call debug command
            print(f"SnapAPI: Executing debug command: {sanitized_cmd_str}")
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
