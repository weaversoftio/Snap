from fastapi import HTTPException
from flows.proccess_utils import run
import uuid
import os
import json
from classes.registryconfig import RegistryConfigDetails, RegistryConfig, login_to_registry, get_registry
from flows.checkpoint.checkpoint_config import CheckpointConfig
from flows.config.configLoder import load_config
from routes.websocket import send_progress

async def create_and_push_checkpoint_container(container_name: str, username: str, pod_name: str, checkpoint_config_name: str, loggeduser: str):
    try:
        await send_progress(loggeduser, {"progress": 12.5,"task_name": "Create and Push Checkpoint Container", "message": f"Create and Push Checkpoint Container {container_name}"})

        # Read metadata from JSON file to get all required variables for new image tag format
        # Use /app/checkpoints/ since we're running inside a container
        checkpoint_dir = f"/app/checkpoints/{pod_name}"
        # Remove .tar extension if present to get the base name for JSON file
        base_name = container_name.replace('.tar', '') if container_name.endswith('.tar') else container_name
        json_file_path = os.path.join(checkpoint_dir, f"{base_name}.json")
        
        print(f"SnapAPI: Looking for JSON metadata file at: {json_file_path}")
        print(f"SnapAPI: Checkpoint directory exists: {os.path.exists(checkpoint_dir)}")
        if os.path.exists(checkpoint_dir):
            files_in_dir = os.listdir(checkpoint_dir)
            print(f"SnapAPI: Files in checkpoint directory: {files_in_dir}")
        
        if not os.path.exists(json_file_path):
            await send_progress(loggeduser, {"progress": "failed","task_name": "Create and Push Checkpoint Container", "message": f"Checkpoint metadata JSON file not found: {json_file_path}"})
            return {"success": False, "message": "Checkpoint metadata JSON file not found"}
        
        # Load metadata from JSON file
        with open(json_file_path, 'r') as f:
            metadata = json.load(f)
        
        # Extract required variables for new image tag format
        cache_registry = metadata["image_info"]["registry"]
        cache_repo = metadata["image_info"]["repository"]
        cluster_norm = metadata["pod_info"]["cluster"].lower()
        namespace = metadata["pod_info"]["namespace"]
        app = metadata["pod_info"]["app"]
        orig_image_short_digest = metadata["image_info"]["original_image_digest"]
        pod_template_hash = metadata["pod_info"]["pod_template_hash"]
        
        print(f"SnapAPI: Extracted metadata for image tag:")
        print(f"  cache_registry: {cache_registry}")
        print(f"  cache_repo: {cache_repo}")
        print(f"  cluster_norm: {cluster_norm}")
        print(f"  namespace: {namespace}")
        print(f"  app: {app}")
        print(f"  orig_image_short_digest: {orig_image_short_digest}")
        print(f"  pod_template_hash: {pod_template_hash}")

        registry_config_name = checkpoint_config_name
        checkpoint_file_name = container_name

        checkpoint_config = get_registry(registry_config_name)
        print(f"checkpoint_config: {checkpoint_config.registry}")

        await login_to_registry(registry_config_name)
        
        if not checkpoint_config:
            await send_progress(loggeduser, {"progress": "failed","task_name": "Create and Push Checkpoint Container", "message": f"Checkpoint config {checkpoint_config_name} not found"})
            return {"success": False, "message": "Checkpoint config not found"}
        
        # Verify registry connectivity
        await send_progress(loggeduser, {"progress": 15,"task_name": "Create and Push Checkpoint Container", "message": f"Verifying registry connectivity"})
        try:
            # Test registry connectivity
            registry_test_result = await run(["curl", "-k", "-s", "-o", "/dev/null", "-w", "%{http_code}", f"{cache_registry}/v2/"], capture_output=True, text=True, check=False)
            print(f"SnapAPI: Registry connectivity test result: {registry_test_result.stdout}")
            if registry_test_result.stdout.strip() not in ["200", "401"]:  # 401 is OK for unauthenticated access
                print(f"SnapAPI: Warning - Registry may not be accessible: HTTP {registry_test_result.stdout}")
        except Exception as e:
            print(f"SnapAPI: Warning - Could not test registry connectivity: {str(e)}")

        # Create new container from scratch
        await send_progress(loggeduser, {"progress": 25,"task_name": "Create and Push Checkpoint Container", "message": f"Creating new container from scratch"})
        newcontainer = (await run(["buildah", "from", "scratch"])).stdout.strip()

        # Add checkpoint tar to container
        await send_progress(loggeduser, {"progress": 37.5,"task_name": "Create and Push Checkpoint Container", "message": f"Addding checkpoint tar to container"})
        # Use the base_name for the TAR file as well
        checkpoint_tar_path = os.path.join(checkpoint_dir, f"{base_name}.tar")
        await run(["buildah", "add", newcontainer, checkpoint_tar_path, "/"])

        # Configure container annotation
        await send_progress(loggeduser, {"progress": 50,"task_name": "Create and Push Checkpoint Container", "message": f"Configuring container annotation"})
        await run([
            "buildah", "config",
            f"--annotation=io.kubernetes.cri-o.annotations.checkpoint.name={base_name}",
            newcontainer
        ])

        # Generate local image tag for buildah commit (without registry URL)
        local_image_tag = f"{cluster_norm}-{namespace}-{app}:{orig_image_short_digest}-{pod_template_hash}"
        
        # Generate registry image tag for buildah operations (without http:// prefix)
        registry_host = cache_registry.replace("http://", "").replace("https://", "")
        buildah_registry_tag = f"{registry_host}/{cache_repo}/{cluster_norm}-{namespace}-{app}:{orig_image_short_digest}-{pod_template_hash}"
        
        # Generate full registry image tag for API response
        full_registry_image_tag = f"{cache_registry}/{cache_repo}/{cluster_norm}-{namespace}-{app}:{orig_image_short_digest}-{pod_template_hash}"
        
        print(f"*************\n")
        print(f"SnapAPI: Using new image tag format:")
        print(f"  cache_registry: {cache_registry}")
        print(f"  cache_repo: {cache_repo}")
        print(f"  cluster_norm: {cluster_norm}")
        print(f"  namespace: {namespace}")
        print(f"  app: {app}")
        print(f"  orig_image_short_digest: {orig_image_short_digest}")
        print(f"  pod_template_hash: {pod_template_hash}")
        print(f"  Local image_tag: {local_image_tag}")
        print(f"  Buildah registry_tag: {buildah_registry_tag}")
        print(f"  Full registry image_tag: {full_registry_image_tag}")
        print(f"\n*************\n")


        # Check container status and disk space before commit
        await send_progress(loggeduser, {"progress": 60,"task_name": "Create and Push Checkpoint Container", "message": f"Checking container status and disk space"})
        try:
            # Check if container exists and is valid
            containers_result = await run(["buildah", "containers"], capture_output=True, text=True, check=False)
            print(f"SnapAPI: Available containers: {containers_result.stdout}")
            
            # Check disk space
            disk_result = await run(["df", "-h", "/"], capture_output=True, text=True, check=False)
            print(f"SnapAPI: Disk space: {disk_result.stdout}")
            
            # Check buildah images
            images_result = await run(["buildah", "images"], capture_output=True, text=True, check=False)
            print(f"SnapAPI: Available images: {images_result.stdout}")
            
        except Exception as e:
            print(f"SnapAPI: Warning - Could not check system status: {str(e)}")

        await send_progress(loggeduser, {"progress": 62.5,"task_name": "Create and Push Checkpoint Container", "message": f"Committing the container image"})
        try:
            commit_result = await run(["buildah", "commit", newcontainer, local_image_tag], capture_output=True, text=True, check=True)
            print(f"SnapAPI: Buildah commit successful: {commit_result.stdout}")
        except RuntimeError as e:
            print(f"SnapAPI: Buildah commit failed: {str(e)}")
            raise

        # Clean up the temporary container
        await send_progress(loggeduser, {"progress": 75,"task_name": "Create and Push Checkpoint Container", "message": f"Cleaning up the temporary container"})
        await run(["buildah", "rm", newcontainer], capture_output=False)

        # Tag the local image with the registry tag
        await send_progress(loggeduser, {"progress": 80,"task_name": "Create and Push Checkpoint Container", "message": f"Tagging image for registry"})
        try:
            tag_result = await run(["buildah", "tag", local_image_tag, buildah_registry_tag], capture_output=True, text=True, check=True)
            print(f"SnapAPI: Buildah tag successful: {tag_result.stdout}")
        except RuntimeError as e:
            print(f"SnapAPI: Buildah tag failed: {str(e)}")
            raise

        # Push the image to the registry
        await send_progress(loggeduser, {"progress": 87.5,"task_name": "Create and Push Checkpoint Container", "message": f"Pushing the image to the registry"})
        try:
            push_result = await run(["buildah", "push", "--tls-verify=false", buildah_registry_tag], capture_output=True, text=True, check=True)
            print(f"SnapAPI: Buildah push successful: {push_result.stdout}")
        except RuntimeError as e:
            print(f"SnapAPI: Buildah push failed: {str(e)}")
            raise

        await send_progress(loggeduser, {"progress": 100,"task_name": "Create and Push Checkpoint Container", "message": f"Checkpoint image successfully committed and pushed"})
        return {"message": "Checkpoint image successfully committed and pushed", "image_tag": full_registry_image_tag}

    except RuntimeError as e:
        await send_progress(loggeduser, {"progress": "failed","task_name": "Create and Push Checkpoint Container", "message": f"Failed with error {str(e)}"})
        raise HTTPException(
            status_code=500,
            detail=f"Error during checkpoint container operation: {str(e)}"
        )
    except Exception as e:
        await send_progress(loggeduser, {"progress": "failed","task_name": "Create and Push Checkpoint Container", "message": f"Failed with error {str(e)}"})
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )
