import os
import subprocess
import json
from fastapi import HTTPException
from classes.apirequests import PodSpecCheckpointRequest, PodCheckpointResponse
from routes.websocket import send_progress

# ----------------------------
# Subprocess helper
# ----------------------------
async def run(command, capture_output=True, text=True, check=True):
    """
    Utility function to run subprocess commands.
    IMPORTANT: To use pipes or shell features, pass:
        run(["/bin/sh", "-lc", "<your shell cmd>"])
    """
    try:
        result = subprocess.run(command, capture_output=capture_output, text=text, check=check)
        return result
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Command failed: {' '.join(command)}\nExitCode: {e.returncode}\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}")

# ----------------------------
# Helpers
# ----------------------------
def _short_digest_from_full(full_digest: str) -> str:
    """
    full_digest like 'sha256:4833e2f3ecd4a163...'
    returns '4833e2f3ecd4'
    """
    if not full_digest:
        return ""
    try:
        return full_digest.split(":")[-1][:12]
    except Exception:
        return full_digest[:12]

async def _skopeo_extract_digest(image_ref: str) -> str:
    """
    image_ref example: docker://docker.io/nginxinc/nginx-unprivileged:stable
    returns full digest like 'sha256:4833e2f3...'
    """
    cmd = ["skopeo", "inspect", image_ref]
    out = await run(cmd)
    data = json.loads(out.stdout)
    return data.get("Digest", "")


# ----------------------------
# Main entrypoint (DROP-IN)
# ----------------------------
async def checkpoint_and_push_combined_from_pod_spec(request: PodSpecCheckpointRequest, username: str) -> dict:
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
        app = labels.get("app")
        pod_template_hash = labels.get("pod-template-hash")

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

        # Validate required fields
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

        # ----- Env/config -----
        snap_cluster = os.getenv("snap_cluster", "crc")          # cluster identifier
        snap_registry = os.getenv("snap_registry", "docker.io")
        snap_repo = os.getenv("snap_repo", "snap_images")
        snap_registry_user = os.getenv("snap_registry_user", "")
        snap_registry_pass = os.getenv("snap_registry_pass", "")
        snap_kube_api_address = os.getenv("snap_kube_api_address", "kubernetes.default.svc")

        # NEW: where our SnapAPI deployment lives (for oc exec / cluster-local service)
        snapapi_namespace = os.getenv("SNAPAPI_NAMESPACE", "snap")
         
        # Dynamically get snapapi service cluster IP
        try:
            svc_cmd = ["oc", "get", "svc", "snapapi", "-n", snapapi_namespace, "-o", "jsonpath={.spec.clusterIP}"]
            svc_result = await run(svc_cmd)
            snapapi_cluster_ip = svc_result.stdout.strip()
            SNAP_API_URL = f"http://{snapapi_cluster_ip}:8000"
            print(f"Dynamically configured SNAP_API_URL: {SNAP_API_URL}")
        except Exception as e:
            # Fallback to environment variable or default
            SNAP_API_URL = os.getenv("SNAP_API_URL", "http://snapapi.apps-crc.testing")
            print(f"Failed to get snapapi cluster IP, using fallback: {SNAP_API_URL}. Error: {e}")

        await send_progress(username, {
            "progress": 5,
            "task_name": "Checkpoint and Push Combined",
            "message": f"Starting combined checkpoint+push for pod: {pod_name}"
        })

        # =========================
        # Phase 1: Create checkpoint
        # =========================
        await send_progress(username, {
            "progress": 10,
            "task_name": "Create Checkpoint",
            "message": "Creating checkpoint via kubelet"
        })

        # Get service account token for kube-api call
        try:
            with open('/var/run/secrets/kubernetes.io/serviceaccount/token', 'r') as f:
                token = f.read().strip()
        except FileNotFoundError:
            token = (await run(["oc", "whoami", "-t"])).stdout.strip()

        # Normalize kube API address
        kube_api_address = snap_kube_api_address
        if kube_api_address.startswith('kubernetes.default.svc'):
            kube_api_address = "https://kubernetes.default.svc:443"
        elif not kube_api_address.startswith("http"):
            kube_api_address = f"https://{kube_api_address}"

        kube_api_checkpoint_url = (
            f"{kube_api_address}/api/v1/nodes/{node_name}/proxy/checkpoint/{namespace}/{pod_name}/{container_name}"
        )
        print(kube_api_checkpoint_url)
        checkpoint_cmd = [
            "curl", "-k", "-X", "POST",
            "--header", f"Authorization: Bearer {token}",
            kube_api_checkpoint_url
        ]
        await send_progress(username, {
            "progress": 30,
            "task_name": "Create Checkpoint",
            "message": f"Calling kubelet checkpoint API for {pod_name}/{container_name}"
        })
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

        await send_progress(username, {
            "progress": 45,
            "task_name": "Create Checkpoint",
            "message": f"Checkpoint created: {checkpoint_file_path}"
        })

        # =========================
        # Phase 1.5: Upload checkpoint file from the node (matching checkpoint_container_kubelet.py)
        # =========================
        await send_progress(username, {
            "progress": 55,
            "task_name": "Create Checkpoint",
            "message": f"Uploading checkpoint file from node: {checkpoint_file_path}"
        })

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
            await send_progress(username, {"progress": 60, "task_name": "Create Checkpoint", "message": f"Uploading checkpoint file..."})
            print(f"Uploading checkpoint from node: {checkpoint_file_path}")
            print(f"Curl Command: {debug_command}")
            print(f"Upload URL: {SNAP_API_URL}/checkpoint/upload/{pod_name}?filename={checkpoint_filename}")
            
            # Add shorter timeout to prevent hanging
            import asyncio
            try:
                debug_output = await asyncio.wait_for(run(debug_command), timeout=90)  # 90 second timeout
            except asyncio.TimeoutError:
                print("Upload timeout after 90 seconds - trying alternative approach")
                raise RuntimeError("Upload timeout - curl command hung")
                
            if debug_output.stdout:
                print(f"Upload result: {debug_output.stdout[:200]}...")
            if debug_output.stderr:
                print(f"Upload stderr: {debug_output.stderr[:200]}...")
            await send_progress(username, {"progress": 65, "task_name": "Create Checkpoint", "message": f"Upload completed"})
            
            if debug_output.returncode != 0:
                error_msg = f"Upload failed: {debug_output.stderr[:100]}..."
                print(error_msg)
                await send_progress(username, {"progress": "failed", "task_name": "Create Checkpoint", "message": f"Error: {error_msg}"})
                return {
                    "success": False,
                    "message": error_msg,
                    "checkpoint_result": None,
                    "push_result": None
                }
        except Exception as e:
            error_msg = f"Upload error: {str(e)}"
            print(error_msg)
            await send_progress(username, {"progress": "failed", "task_name": "Create Checkpoint", "message": f"Error: {error_msg}"})
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
        await send_progress(username, {
            "progress": 72,
            "task_name": "Create and Push Checkpoint Container",
            "message": "Preparing buildah container"
        })

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
        cluster_norm = (snap_cluster or "").lower()
        image_tag = f"{snap_registry}/{snap_repo}/{cluster_norm}-{namespace}-{app}:{orig_image_short_digest}-{pod_template_hash}"

        # Registry login (optional)
        if snap_registry_user and snap_registry_pass:
            try:
                await run(["buildah", "login", "--username", snap_registry_user, "--password", snap_registry_pass, snap_registry], check=True)
            except Exception as e:
                # Log but continue (might be a public/insecure registry)
                await send_progress(username, {
                    "progress": 74,
                    "task_name": "Create and Push Checkpoint Container",
                    "message": f"Registry login failed (continuing): {e}"
                })

        # Create scratch container, add checkpoint bits, annotate, commit, push
        newcontainer = (await run(["buildah", "from", "scratch"])).stdout.strip()
        try:
            await run(["buildah", "add", newcontainer, f"./checkpoints/{pod_name}/{container_name}", "/"])
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

        await send_progress(username, {
            "progress": 90,
            "task_name": "Create and Push Checkpoint Container",
            "message": f"Pushing image: {image_tag}"
        })

        # Push
        await run(["buildah", "push", "--tls-verify=false", image_tag], capture_output=True, text=True, check=True)

        await send_progress(username, {
            "progress": 100,
            "task_name": "Create and Push Checkpoint Container",
            "message": "Checkpoint image successfully committed and pushed"
        })

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
        await send_progress(username, {
            "progress": "failed",
            "task_name": "Checkpoint and Push Combined",
            "message": err
        })
        return {
            "success": False,
            "message": err,
            "checkpoint_result": None,
            "push_result": None
        }
