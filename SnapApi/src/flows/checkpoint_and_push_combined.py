import os
import json
from fastapi import HTTPException
from classes.apirequests import PodSpecCheckpointRequest, PodCheckpointResponse
from flows.proccess_utils import run
from flows.helpers import _short_digest_from_full, _skopeo_extract_digest, extract_app_name_from_pod, get_snap_config_from_cluster_cache_api


# ----------------------------
# Main entrypoint (DROP-IN)
# ----------------------------
async def checkpoint_and_push_combined_from_pod_spec(request: PodSpecCheckpointRequest, cluster: str, username: str) -> dict:
    """
    Combined function that performs both checkpoint creation and container push from pod spec.
    NOW USING CLUSTER-NATIVE UPLOAD PATH:
      - node -> SnapAPI pod via oc exec
      - curl to localhost:8000 inside SnapAPI pod (no host DNS/route reliance)
    """
    try:
        # ----- Extract pod spec fields -----
        pod_spec = request.pod_spec
        metadata = pod_spec.get("metadata", {})
        spec = pod_spec.get("spec", {})
        labels = metadata.get("labels", {})
        containers = spec.get("containers", [])

        pod_name = metadata.get("name")
        namespace = metadata.get("namespace")
        node_name = spec.get("nodeName")
        
        # If pod_name is None or empty, try to use generateName
        if not pod_name:
            generate_name = metadata.get("generateName", "")
            if generate_name:
                # Remove trailing dash from generateName
                pod_name = generate_name.rstrip("-")
                print(f"DEBUG - Checkpoint using generateName: '{generate_name}' -> pod_name: '{pod_name}'")
        
        # Extract app name using helper function
        app = extract_app_name_from_pod(pod_name, labels)
            
        pod_template_hash = labels.get("pod-template-hash", "")
        
        # Provide default value for pod_template_hash if empty
        if not pod_template_hash:
            pod_template_hash = "no-hash"

        if not containers:
            raise ValueError("No containers found in pod spec")

        container = containers[0]
        container_name = container.get("name")
        container_image = container.get("image", "")

        # Only set this if image has @digest (many pods are tag-based)
        orig_image_short_digest = ""
        if "@" in container_image:
            try:
                orig_image_short_digest = container_image.split("@", 1)[1].split(":")[-1][:12]
            except Exception:
                orig_image_short_digest = ""

        # Validate required fields (now with defaults applied)
        required_fields = {
            "pod_name": pod_name,
            "namespace": namespace,
            "node_name": node_name,
            "container_name": container_name,
            "app": app,
            "pod_template_hash": pod_template_hash,
        }
        missing = [k for k, v in required_fields.items() if not v]
        if missing:
            raise ValueError(f"Missing required fields from pod spec: {missing}")

        # ----- Load configuration from cache -----
        snap_config = await get_snap_config_from_cluster_cache_api(cluster)
        cache_registry = snap_config["cache_registry"]
        cache_registry_user = snap_config["cache_registry_user"]
        cache_registry_pass = snap_config["cache_registry_pass"]
        cache_repo = snap_config["cache_repo"]
        kube_api_address = snap_config["kube_api_address"]
        kube_username = snap_config["kube_username"]
        kube_password = snap_config["kube_password"]
        auth_method = snap_config["auth_method"]

         
        SNAP_API_URL = os.getenv("SNAP_API_URL", "Unknown")


        # =========================
        # Phase 1: Create checkpoint
        # =========================


        # Get authentication credentials from cluster cache
        # Normalize kube API address
        if kube_api_address.startswith('kubernetes.default.svc'):
            kube_api_address = "https://kubernetes.default.svc:443"
        elif not kube_api_address.startswith("http"):
            kube_api_address = f"https://{kube_api_address}"

        kube_api_checkpoint_url = (
            f"{kube_api_address}/api/v1/nodes/{node_name}/proxy/checkpoint/{namespace}/{pod_name}/{container_name}"
        )
        print(kube_api_checkpoint_url)
        
        # Get proper Bearer token for authentication
        if auth_method == "token":
            # Use provided token directly
            token = kube_password
        else:
            # For username/password auth, we need to get a Bearer token
            # First try to login and get token using oc
            try:
                # Login using kubeadmin credentials and get token
                login_cmd = ["oc", "login", kube_api_address, "-u", kube_username, "-p", kube_password, "--insecure-skip-tls-verify=true"]
                await run(login_cmd)
                
                # Get the token
                token_cmd = ["oc", "whoami", "--show-token"]
                token_output = await run(token_cmd)
                token = token_output.stdout.strip()
            except Exception as e:
                print(f"Failed to get token via oc login: {e}")
                # Fallback to using password as token (may work in some cases)
                token = kube_password
        
        # Build curl command with Bearer token
        checkpoint_cmd = [
            "curl", "-k", "-X", "POST",
            "--header", f"Authorization: Bearer {token}",
            kube_api_checkpoint_url
        ]

        print(f"Creating checkpoint: {pod_name}/{container_name}")
        print(f"Checkpoint API URL: {kube_api_checkpoint_url}")
        
        output = await run(checkpoint_cmd)
        stdout = (output.stdout or "").strip()
        stderr = (output.stderr or "").strip()
        
        print(f"Checkpoint API response: {stdout[:200]}...")
        if stderr:
            print(f"Checkpoint API stderr: {stderr[:200]}...")

        # Parse kubelet response
        try:
            checkpoint_data = json.loads(stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"Checkpoint API did not return JSON.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")

        items = checkpoint_data.get("items") or []
        if not items:
            raise RuntimeError(f"No checkpoint file path found in API response.\n{stdout}")

        checkpoint_file_path = items[0]
        checkpoint_filename = os.path.basename(checkpoint_file_path)
        
        print(f"Checkpoint created at: {checkpoint_file_path}")



        # =========================
        # Phase 1.5: Upload checkpoint file from the node (matching checkpoint_container_kubelet.py)
        # =========================


        # Upload the checkpoint file from the node - use the dynamically configured SNAP_API_URL
        # (SNAP_API_URL was already set above with the cluster IP)
        debug_command = [
            "oc", "debug", f"node/{node_name}", "--",
            "chroot", "/host", "curl", "-X", "POST",
            f"{SNAP_API_URL}/checkpoint/upload/{pod_name}?filename={checkpoint_filename}",
            "-H", "accept: application/json",
            "-H", "Content-Type: multipart/form-data",
            "-F", f"file=@{checkpoint_file_path}"
        ]
        try:
            print(f"Uploading checkpoint from node: {checkpoint_file_path}")
            print(f"Curl Command: {debug_command}")
            print(f"Upload URL: {SNAP_API_URL}/checkpoint/upload/{pod_name}?filename={checkpoint_filename}")
            
            # Call debug command
            print(f"Executing debug command: {debug_command}")
            debug_output = await run(debug_command)
            
            if debug_output.stdout:
                print(f"Upload result: {debug_output.stdout[:200]}...")
            if debug_output.stderr:
                print(f"Upload stderr: {debug_output.stderr[:200]}...")
            
            if debug_output.returncode != 0:
                error_msg = f"Upload failed: {debug_output.stderr[:100]}..."
                print(error_msg)
                return {
                    "success": False,
                    "message": error_msg,
                    "checkpoint_result": None,
                    "push_result": None
                }
        except Exception as e:
            error_msg = f"Upload error: {str(e)}"
            print(error_msg)
            return {
                "success": False,
                "message": error_msg,
                "checkpoint_result": None,
                "push_result": None
            }

        checkpoint_response = PodCheckpointResponse(
            success=True,
            message=f"All containers checkpointed successfully for pod: {pod_name}",
            checkpoint_path=checkpoint_file_path,
            pod_name=pod_name,
            container_ids=container_name,
        )

        # =========================
        # Phase 2: Build & Push image
        # =========================

        # Resolve digest with skopeo if we don't have one from the image string
        if not orig_image_short_digest:
            # Build an inspectable reference for skopeo (docker://…)
            # Example for a tagged image: docker://docker.io/nginxinc/nginx-unprivileged:stable
            image_ref = container_image
            if "://" not in image_ref:
                # assume docker transport if not specified
                image_ref = f"docker://{image_ref}"
            full_digest = await _skopeo_extract_digest(image_ref)
            orig_image_short_digest = _short_digest_from_full(full_digest)

        # Normalize cluster casing to avoid CRC vs crc mismatches
        cluster_norm = cluster.lower()
        image_tag = f"{cache_registry}/{cache_repo}/{cluster_norm}-{namespace}-{app}:{orig_image_short_digest}-{pod_template_hash}"

        # Registry login (optional)
        if cache_registry_user and cache_registry_pass:
            await run(["buildah", "login", "--username", cache_registry_user, "--password", cache_registry_pass, "--tls-verify=false", cache_registry], check=True)


        # Create scratch container, add checkpoint bits, annotate, commit, push
        newcontainer = (await run(["buildah", "from", "scratch"])).stdout.strip()
        try:
            # Use the processed filename instead of container name
            processed_filename = checkpoint_filename.replace('-', '_').replace(':', '_').replace('+', '_')
            if not processed_filename.endswith('.tar'):
                processed_filename = f"{processed_filename}.tar"
            
            checkpoint_file_in_pod = f"./checkpoints/{pod_name}/{processed_filename}"
            print(f"Looking for checkpoint file at: {checkpoint_file_in_pod}")
            
            await run(["buildah", "add", newcontainer, checkpoint_file_in_pod, "/"])
            await run([
                "buildah", "config",
                f"--annotation=io.kubernetes.cri-o.annotations.checkpoint.name={container_name}",
                newcontainer
            ])
            await run(["buildah", "commit", newcontainer, image_tag])
        finally:
            # Ensure container is removed even if commit fails
            try:
                await run(["buildah", "rm", newcontainer], capture_output=False, check=False)
            except Exception:
                pass


        # Push
        await run(["buildah", "push", "--tls-verify=false", image_tag], capture_output=True, text=True, check=True)

        push_result = {"message": "Checkpoint image successfully committed and pushed", "image_tag": image_tag}

        return {
            "success": True,
            "message": "Combined checkpoint and push operation completed successfully",
            "checkpoint_result": checkpoint_response.dict(),
            "push_result": push_result,
            "image_tag": image_tag,
            "pod_name": pod_name,
            "container_name": container_name
        }

    except Exception as e:
        err = f"Combined operation failed: {e}"
        return {
            "success": False,
            "message": err,
            "checkpoint_result": None,
            "push_result": None
        }
