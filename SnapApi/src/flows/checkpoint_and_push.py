import os
import json
from fastapi import HTTPException
from classes.apirequests import PodSpecCheckpointRequest, PodCheckpointResponse
from flows.proccess_utils import run
from flows.helpers import _short_digest_from_full, _skopeo_extract_digest, extract_app_name_from_pod, get_snap_config_from_cluster_cache_api, create_checkpoint_metadata_json
from routes.websocket import broadcast_progress


# ----------------------------
# Main entrypoint (DROP-IN)
# ----------------------------
async def checkpoint_and_push_from_pod_spec(request: PodSpecCheckpointRequest, cluster: str, username: str) -> dict:
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
        node_name = spec.get("node_name") or spec.get("nodeName")  # Try snake_case first, then camelCase
        
        # If pod_name is None or empty, try to use generateName
        if not pod_name:
            generate_name = metadata.get("generateName", "")
            if generate_name:
                # Remove trailing dash from generateName
                pod_name = generate_name.rstrip("-")
                print(f"SnapAPI: DEBUG - Checkpoint using generateName: '{generate_name}' -> pod_name: '{pod_name}'")
        
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
        await broadcast_progress({
            "progress": 20, 
            "task_name": "SnapWatcher Checkpoint", 
            "message": f"Loading cluster configuration for {cluster}"
        })
        
        snap_config = await get_snap_config_from_cluster_cache_api(cluster)
        cache_registry = snap_config["cache_registry"]
        cache_registry_user = snap_config["cache_registry_user"]
        cache_registry_pass = snap_config["cache_registry_pass"]
        cache_repo = snap_config["cache_repo"]
        kube_api_address = snap_config["kube_api_address"]
        token = snap_config["token"]

         
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
        print(f"SnapAPI: {kube_api_checkpoint_url}")
        
        # Use provided token directly
        print("SnapAPI: Using provided token for authentication")
        print(f"SnapAPI: Token: {token[:20]}...")
        
        # Build curl command with Bearer token
        checkpoint_cmd = [
            "curl", "-k", "-X", "POST",
            "--header", f"Authorization: Bearer {token}",
            kube_api_checkpoint_url
        ]

        await broadcast_progress({
            "progress": 30, 
            "task_name": "SnapWatcher Checkpoint", 
            "message": f"Creating checkpoint for {pod_name}/{container_name}"
        })
        
        print(f"SnapAPI: Creating checkpoint: {pod_name}/{container_name}")
        print(f"SnapAPI: Checkpoint API URL: {kube_api_checkpoint_url}")
        
        output = await run(checkpoint_cmd)
        stdout = (output.stdout or "").strip()
        stderr = (output.stderr or "").strip()
        
        print(f"SnapAPI: Checkpoint API response: {stdout[:200]}...")
        if stderr:
            print(f"SnapAPI: Checkpoint API stderr: {stderr[:200]}...")

        # Check for error responses before attempting JSON parsing
        # Error responses from kubelet/CRI-O are plain text, not JSON
        stdout_lower = stdout.lower()
        if ("checkpointing of" in stdout_lower and "failed" in stdout_lower) or \
           "rpc error" in stdout_lower or \
           "code = unknown desc =" in stdout_lower:
            # This is an error response, extract and format the error message
            error_message = stdout.strip()
            # Try to extract a more concise error message if possible
            if "rpc error: code = Unknown desc =" in error_message:
                # Extract the description part after "desc ="
                try:
                    desc_start = error_message.find("desc =") + len("desc =")
                    error_message = error_message[desc_start:].strip()
                except:
                    pass
            
            formatted_error = f"Checkpoint failed: {error_message}"
            await broadcast_progress({
                "progress": "failed", 
                "task_name": "SnapWatcher Checkpoint", 
                "message": formatted_error
            })
            raise RuntimeError(formatted_error)

        # Parse kubelet response
        try:
            checkpoint_data = json.loads(stdout)
        except json.JSONDecodeError:
            error_msg = f"Checkpoint API did not return JSON.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
            await broadcast_progress({
                "progress": "failed", 
                "task_name": "SnapWatcher Checkpoint", 
                "message": f"Checkpoint creation failed: Invalid JSON response"
            })
            raise RuntimeError(error_msg)

        items = checkpoint_data.get("items") or []
        if not items:
            error_msg = f"No checkpoint file path found in API response.\n{stdout}"
            await broadcast_progress({
                "progress": "failed", 
                "task_name": "SnapWatcher Checkpoint", 
                "message": f"Checkpoint creation failed: No checkpoint file path in response"
            })
            raise RuntimeError(error_msg)

        checkpoint_file_path = items[0]
        checkpoint_filename = os.path.basename(checkpoint_file_path)
        
        await broadcast_progress({
            "progress": 40, 
            "task_name": "SnapWatcher Checkpoint", 
            "message": f"Checkpoint created successfully at {checkpoint_file_path}"
        })
        
        print(f"SnapAPI: Checkpoint created at: {checkpoint_file_path}")



        # =========================
        # Phase 1.5: Upload checkpoint file from the node (matching checkpoint_container_kubelet.py)
        # =========================


        # Upload the checkpoint file from the node - use the dynamically configured SNAP_API_URL
        # (SNAP_API_URL was already set above with the cluster IP)
        # First, ensure we're logged in to the cluster for oc debug command
        try:
            from classes.clusterconfig import ClusterConfig
            cluster_config_path = f"config/clusters/{cluster}.json"
            if os.path.exists(cluster_config_path):
                with open(cluster_config_path, "r") as f:
                    cluster_config = ClusterConfig.model_validate_json(f.read())
                
                kube_api_url = cluster_config.cluster_config_details.kube_api_url
                token = cluster_config.cluster_config_details.token
                verify_ssl = os.getenv('KUBE_VERIFY_SSL', 'false').lower() == 'true'
                
                # Login to cluster before running oc debug
                login_cmd = [
                    "oc", "login", 
                    "--token", token,
                    "--server", kube_api_url
                ]
                if not verify_ssl:
                    login_cmd.append("--insecure-skip-tls-verify=true")
                
                print(f"SnapAPI: Logging in to cluster {cluster} for oc debug command")
                await run(login_cmd, check=False)  # Don't fail if already logged in
        except Exception as login_err:
            print(f"SnapAPI: Warning - Could not login to cluster (may already be logged in): {login_err}")
        
        debug_command = [
            "oc", "debug", f"node/{node_name}", "--",
            "chroot", "/host", "curl", "-X", "POST",
            f"{SNAP_API_URL}/checkpoint/upload/{pod_name}?filename={checkpoint_filename}",
            "-H", "accept: application/json",
            "-H", "Content-Type: multipart/form-data",
            "-F", f"file=@{checkpoint_file_path}"
        ]
        try:
            await broadcast_progress({
                "progress": 50, 
                "task_name": "SnapWatcher Checkpoint", 
                "message": f"Uploading checkpoint file from node"
            })
            
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
                await broadcast_progress({
                    "progress": "failed", 
                    "task_name": "SnapWatcher Checkpoint", 
                    "message": f"Upload failed: {debug_output.stderr[:100]}..."
                })
                print(f"SnapAPI: {error_msg}")
                return {
                    "success": False,
                    "message": error_msg,
                    "checkpoint_result": None,
                    "push_result": None
                }
        except Exception as e:
            error_msg = f"Upload error: {str(e)}"
            await broadcast_progress({
                "progress": "failed", 
                "task_name": "SnapWatcher Checkpoint", 
                "message": f"Upload error: {str(e)}"
            })
            print(f"SnapAPI: {error_msg}")
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
        # Phase 1.6: Create checkpoint metadata JSON file
        # =========================
        
        # Generate the image tag that will be used (same logic as later in the code)
        cluster_norm = cluster.lower()
        image_tag = f"{cache_registry}/{cache_repo}/{cluster_norm}-{namespace}-{app}:{orig_image_short_digest}-{pod_template_hash}"
        
        # Create JSON metadata file locally in SnapAPI container
        try:
            await broadcast_progress({
                "progress": 55, 
                "task_name": "SnapWatcher Checkpoint", 
                "message": f"Creating checkpoint metadata file"
            })
            
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
                    "cluster": cluster,
                    "pod_template_hash": pod_template_hash,
                    "node_name": node_name,
                },
                "generation_info": {
                    "image_tag_format": f"{cache_registry}/{cache_repo}/{cluster.lower()}-{namespace}-{app}:{orig_image_short_digest}-{pod_template_hash}",
                    "cluster_normalized": cluster.lower(),
                }
            }
            
            # Create JSON file locally in SnapAPI container
            # Ensure base checkpoints directory exists first
            base_checkpoints_dir = "/app/checkpoints"
            try:
                os.makedirs(base_checkpoints_dir, exist_ok=True)
            except PermissionError as e:
                raise PermissionError(
                    f"Cannot create or access checkpoints directory {base_checkpoints_dir}. "
                    f"Please ensure the directory exists and is writable by the snap user (UID 669). "
                    f"Original error: {e}"
                )
            
            local_checkpoint_path = f"{base_checkpoints_dir}/{pod_name}"
            try:
                os.makedirs(local_checkpoint_path, exist_ok=True)
            except PermissionError as e:
                raise PermissionError(
                    f"Cannot create checkpoint directory {local_checkpoint_path}. "
                    f"Please ensure {base_checkpoints_dir} is writable by the snap user (UID 669). "
                    f"Original error: {e}"
                )
            
            # Generate JSON file path locally with normalized filename
            json_filename = os.path.splitext(checkpoint_filename)[0] + ".json"
            json_filename = json_filename.replace('-', '_').replace(':', '_').replace('+', '_')
            json_file_path = os.path.join(local_checkpoint_path, json_filename)
            
            # Write JSON file locally
            with open(json_file_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            print(f"SnapAPI: Checkpoint metadata JSON created locally at: {json_file_path}")
            
        except Exception as e:
            print(f"SnapAPI: Warning - Failed to create checkpoint metadata JSON: {e}")
            # Don't fail the entire operation if JSON creation fails
            json_file_path = None

        # =========================
        # Phase 2: Build & Push image
        # =========================

        await broadcast_progress({
            "progress": 60, 
            "task_name": "SnapWatcher Checkpoint", 
            "message": f"Building checkpoint image"
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
        cluster_norm = cluster.lower()
        
        # Strip protocol prefix from cache_registry for buildah operations
        # buildah commit/push don't accept URLs with http:// or https://
        registry_host = cache_registry.replace("http://", "").replace("https://", "")
        buildah_image_tag = f"{registry_host}/{cache_repo}/{cluster_norm}-{namespace}-{app}:{orig_image_short_digest}-{pod_template_hash}"
        
        # Keep full URL version for API response
        full_image_tag = f"{cache_registry}/{cache_repo}/{cluster_norm}-{namespace}-{app}:{orig_image_short_digest}-{pod_template_hash}"

        # Registry login (optional)
        if cache_registry_user and cache_registry_pass:
            await run(["buildah", "login", "--username", cache_registry_user, "--password", cache_registry_pass, "--tls-verify=false", cache_registry], check=True)


        # Create scratch container, add checkpoint bits, annotate, commit, push
        print(f"SnapAPI: DEBUG - Creating scratch container...")
        newcontainer = (await run(["buildah", "from", "scratch"])).stdout.strip()
        print(f"SnapAPI: DEBUG - Created container: {newcontainer}")
        
        try:
            # Use the processed filename instead of container name
            processed_filename = checkpoint_filename.replace('-', '_').replace(':', '_').replace('+', '_')
            if not processed_filename.endswith('.tar'):
                processed_filename = f"{processed_filename}.tar"
            
            checkpoint_file_in_pod = f"/app/checkpoints/{pod_name}/{processed_filename}"
            print(f"SnapAPI: Looking for checkpoint file at: {checkpoint_file_in_pod}")
            
            # Check if file exists before trying to add it
            if not os.path.exists(checkpoint_file_in_pod):
                raise RuntimeError(f"Checkpoint file does not exist at: {checkpoint_file_in_pod}")
            file_size = os.path.getsize(checkpoint_file_in_pod)
            print(f"SnapAPI: DEBUG - Checkpoint file exists, size: {file_size} bytes")
            
            print(f"SnapAPI: DEBUG - Adding checkpoint file to container...")
            await run(["buildah", "add", newcontainer, checkpoint_file_in_pod, "/"])
            print(f"SnapAPI: DEBUG - Checkpoint file added successfully")
            
            print(f"SnapAPI: DEBUG - Configuring container annotations...")
            await run([
                "buildah", "config",
                f"--annotation=io.kubernetes.cri-o.annotations.checkpoint.name={container_name}",
                newcontainer
            ])
            print(f"SnapAPI: DEBUG - Container configured successfully")
            
            print(f"SnapAPI: DEBUG - Committing container to image: {buildah_image_tag}")
            commit_output = await run(["buildah", "commit", newcontainer, buildah_image_tag])
            print(f"SnapAPI: DEBUG - Container committed successfully")
            print(f"SnapAPI: DEBUG - Commit output: {commit_output.stdout[:200] if commit_output.stdout else 'None'}")
        except RuntimeError as e:
            print(f"SnapAPI: DEBUG - Build step failed with RuntimeError: {str(e)}")
            raise
        except Exception as e:
            print(f"SnapAPI: DEBUG - Build step failed with unexpected error: {type(e).__name__}: {str(e)}")
            raise
        finally:
            # Ensure container is removed even if commit fails
            print(f"SnapAPI: DEBUG - Cleaning up container: {newcontainer}")
            try:
                await run(["buildah", "rm", newcontainer], capture_output=False, check=False)
                print(f"SnapAPI: DEBUG - Container removed successfully")
            except Exception as e:
                print(f"SnapAPI: DEBUG - Warning: Failed to remove container: {str(e)}")
                pass

        await broadcast_progress({
            "progress": 80, 
            "task_name": "SnapWatcher Checkpoint", 
            "message": f"Pushing checkpoint image to registry"
        })

        # Push
        print(f"SnapAPI: DEBUG - About to push image: {buildah_image_tag}")
        print(f"SnapAPI: DEBUG - Full image tag: {full_image_tag}")
        print(f"SnapAPI: DEBUG - Registry: {cache_registry}")
        print(f"SnapAPI: DEBUG - Registry host (buildah): {registry_host}")
        print(f"SnapAPI: DEBUG - Starting buildah push command...")
        try:
            push_output = await run(["buildah", "push", "--tls-verify=false", buildah_image_tag], capture_output=True, text=True, check=True)
            print(f"SnapAPI: DEBUG - Buildah push completed successfully")
            print(f"SnapAPI: DEBUG - Push stdout: {push_output.stdout[:500] if push_output.stdout else 'None'}")
            print(f"SnapAPI: DEBUG - Push stderr: {push_output.stderr[:500] if push_output.stderr else 'None'}")
        except RuntimeError as e:
            print(f"SnapAPI: DEBUG - Buildah push failed with RuntimeError: {str(e)}")
            raise
        except Exception as e:
            print(f"SnapAPI: DEBUG - Buildah push failed with unexpected error: {type(e).__name__}: {str(e)}")
            raise

        push_result = {"message": "Checkpoint image successfully committed and pushed", "image_tag": full_image_tag}

        return {
            "success": True,
            "message": "Combined checkpoint and push operation completed successfully",
            "checkpoint_result": checkpoint_response.dict(),
            "push_result": push_result,
            "image_tag": image_tag,
            "pod_name": pod_name,
            "container_name": container_name,
            "metadata_json_path": json_file_path
        }

    except Exception as e:
        err = f"Combined operation failed: {e}"
        await broadcast_progress({
            "progress": "failed", 
            "task_name": "SnapWatcher Checkpoint", 
            "message": f"Operation failed: {str(e)}"
        })
        return {
            "success": False,
            "message": err,
            "checkpoint_result": None,
            "push_result": None
        }
