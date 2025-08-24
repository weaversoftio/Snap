from fastapi import HTTPException
from flows.proccess_utils import run
import uuid
import os
from classes.registryconfig import RegistryConfigDetails, RegistryConfig, login_to_registry, get_registry
from flows.checkpoint.checkpoint_config import CheckpointConfig
from flows.config.configLoder import load_config
from routes.websocket import send_progress

async def create_and_push_checkpoint_container(container_name: str, username: str, pod_name: str, checkpoint_config_name: str, loggeduser: str):
    try:
        await send_progress(loggeduser, {"progress": 12.5,"task_name": "Create and Push Checkpoint Container", "message": f"Create and Push Checkpoint Container {container_name}"})

        registry_config_name = checkpoint_config_name
        checkpoint_file_name = container_name


        checkpoint_config = get_registry(registry_config_name)

        print(f"checkpoint_config: {checkpoint_config.registry}")

        await login_to_registry(registry_config_name)
        
        
        
        if not checkpoint_config:
            await send_progress(loggeduser, {"progress": "failed","task_name": "Create and Push Checkpoint Container", "message": f"Checkpoint config {checkpoint_config_name} not found"})
            return {"success": False, "message": "Checkpoint config not found"}

        # Create new container from scratch
        await send_progress(loggeduser, {"progress": 25,"task_name": "Create and Push Checkpoint Container", "message": f"Creating new container from scratch"})
        newcontainer = (await run(["buildah", "from", "scratch"])).stdout.strip()

        # Add checkpoint tar to container
        await send_progress(loggeduser, {"progress": 37.5,"task_name": "Create and Push Checkpoint Container", "message": f"Addding checkpoint tar to container"})
        await run(["buildah", "add", newcontainer, f"./checkpoints/{pod_name}/{checkpoint_file_name}", "/"])

        # Configure container annotation
        await send_progress(loggeduser, {"progress": 50,"task_name": "Create and Push Checkpoint Container", "message": f"Configuring container annotation"})
        await run([
            "buildah", "config",
            f"--annotation=io.kubernetes.cri-o.annotations.checkpoint.name={checkpoint_file_name}",
            newcontainer
        ])

        # Generate a short UUID for the image tag
        short_uid = str(uuid.uuid4())[:8]
        # Construct the full image tag using the registry URL
        image_tag = f"{checkpoint_config.registry.rstrip('/')}/{pod_name[:6].rstrip('-')}-{checkpoint_file_name[:6].rstrip('-')}:{short_uid}"
        print(f"*************\n")
        print(f"checkpoint_config.registry: {checkpoint_config.registry}")
        print(f"checkpoint_config.registry_rstrip: {checkpoint_config.registry.rstrip('/')}\n")
        print(f"pod_name: {pod_name}")
        print(f"pod_name_short_rstrip: {pod_name[:6].rstrip('-')}\n")
        print(f"checkpoint_file_name: {checkpoint_file_name}")
        print(f"checkpoint_file_name_short_rstrip: {checkpoint_file_name[:6].rstrip('-')}\n")
        print(f"short_uid: {short_uid}\n")
        print(f"image_tag: {image_tag}")
        print(f"\n*************\n")


        await send_progress(loggeduser, {"progress": 62.5,"task_name": "Create and Push Checkpoint Container", "message": f"Committing the container image"})
        await run(["buildah", "commit", newcontainer, image_tag])

        # Clean up the temporary container
        await send_progress(loggeduser, {"progress": 75,"task_name": "Create and Push Checkpoint Container", "message": f"Cleaning up the temporary container"})
        await run(["buildah", "rm", newcontainer], capture_output=False)

        # Push the image to the registry
        await send_progress(loggeduser, {"progress": 87.5,"task_name": "Create and Push Checkpoint Container", "message": f"Pushing the image to the registry"})
        await run(["buildah", "push", "--tls-verify=false", image_tag], capture_output=True, text=True, check=True)

        await send_progress(loggeduser, {"progress": 100,"task_name": "Create and Push Checkpoint Container", "message": f"Checkpoint image successfully committed and pushed"})
        return {"message": "Checkpoint image successfully committed and pushed", "image_tag": image_tag}

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
