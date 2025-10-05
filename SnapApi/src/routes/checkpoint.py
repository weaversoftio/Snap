import os
import json
import logging
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from fastapi.responses import FileResponse
import shutil
from classes.apirequests import PodCheckpointRequest, CheckpointctlRequest, PodCheckpointAndPushRequest, PodSpecCheckpointRequest
from flows.checkpoint_container_kubelet import checkpoint_container_kubelet
from flows.checkpoint_and_push import checkpoint_and_push_from_pod_spec
from flows.proccess_utils import run
from flows.upload_checkpoint import upload_checkpoint
from flows.analytics.checkpoint_insights import CheckpointInsightsUseCase, CheckpointInsightsRequest
from flows.analytics.analyze_checkpoint_volatility import analyze_checkpoint_volatility, VolatilityRequest, checkpoint_volatility_analysis
from middleware.verify_token import verify_token
from routes.websocket import send_progress

router = APIRouter()
logger = logging.getLogger("automation_api")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
checkpoint_path = os.path.join(BASE_DIR, 'checkpoints')

@router.post("/kubelet/checkpoint")
async def create_checkpoint_kubelet(request: PodCheckpointRequest, username: str = Depends(verify_token)):
    return await checkpoint_container_kubelet(request, username)

@router.post("/kubelet/checkpoint-and-push")
async def create_checkpoint_and_push_combined(
    request: PodCheckpointAndPushRequest, 
    pod_name: str,
    node_name: str,
    container_name: str,
    checkpoint_config_name: str,
    username: str = Depends(verify_token)
):
    """
    Combined endpoint that creates a checkpoint via kubelet and then creates and pushes a container image.
    This performs both operations in a single API call with new tagging format.
    Required parameters are passed as query parameters or path parameters.
    """
    
    # Create a PodCheckpointRequest for the checkpoint operation
    checkpoint_request = PodCheckpointRequest(
        pod_name=pod_name,
        namespace=request.namespace,
        node_name=node_name,
        container_name=container_name,
        cluster_name=request.cluster
    )
    
    # Call the combined function with new tagging parameters
    return await checkpoint_and_push_combined(
        checkpoint_request, 
        checkpoint_config_name, 
        username,
        cluster=request.cluster,
        namespace=request.namespace,
        app=request.app,
        origImageShortDigest=request.origImageShortDigest,
        PodTemplateHash=request.PodTemplateHash
    )

@router.post("/pod-spec/checkpoint-and-push")
async def create_checkpoint_and_push_from_pod_spec(
    request: PodSpecCheckpointRequest,
    username: str = Depends(verify_token)
):
    """
    New combined endpoint that creates a checkpoint via kubelet and then creates and pushes a container image.
    Extracts all required information from the pod specification and environment variables.
    Uses environment variables for registry configuration and cluster information.
    """
    return await checkpoint_and_push_from_pod_spec(request, username)



@router.get("/list")
async def checkpoints_list():
    checkpoint_dir = checkpoint_path
    try:
        if os.path.exists(checkpoint_dir):
            pod_container_mapping = []
            for pod in os.listdir(checkpoint_dir):
                pod_path = os.path.join(checkpoint_dir, pod)
                if os.path.isdir(pod_path):
                    containers = os.listdir(pod_path)
                    logger.info(f"SnapAPI: {containers}")
                    for container in containers:
                        if container.endswith(".tar"):
                            volatility_analysis_file = os.path.join(pod_path, f"{container.replace('.tar', '')}_volatility_analysis.txt")
                            analysis_result = f"{container.replace('.tar', '')}.json"
                            analysis_result_path = os.path.join(pod_path, analysis_result)
                            pod_container_mapping.append({
                                "pod_name": pod,
                                "checkpoint_name": container,
                                "analysis_result": analysis_result if os.path.exists(analysis_result_path) else None,
                                "scan_result": os.path.exists(volatility_analysis_file)
                            })

                        
            return {"checkpoints": pod_container_mapping}
        else:
            return {"checkpoints": [], "message": "Checkpoint directory does not exist"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading checkpoint directory: {str(e)}")

@router.post("/upload/{pod_name}")
async def upload_checkpoint_route(pod_name: str, file: UploadFile = File(...)):
    try:
        # Extract filename from the Content-Disposition header
        content_disposition = file.headers.get("content-disposition", "")
        filename = None
        if "filename=" in content_disposition:
            filename = content_disposition.split("filename=")[1].strip('"')
        
        if not filename:
            raise HTTPException(status_code=400, detail="No filename found in upload")
            
        print(f"Uploading: {filename}")
        result = upload_checkpoint(file.file, checkpoint_path, pod_name, filename)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.get("/download/{pod_name}")
async def download_checkpoint_route(pod_name: str, filename: str):
    try:
        file_path = os.path.join(checkpoint_path, pod_name, filename)

        if not os.path.isfile(file_path):
            raise HTTPException(status_code=404, detail="Checkpoint file not found")

        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/octet-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")

@router.post("/checkpointctl")
async def checkpointctl(request: CheckpointctlRequest, username: str = Depends(verify_token)):
    try:
        await send_progress(username, {"progress": 35, "task_name": "Inspecting Checkpoint", "message": f"Inspecting checkpoint initiated"})
        pod_name = request.pod_name
        checkpoint_name = request.checkpoint_name
        checkpoint_dir = os.path.join(checkpoint_path, pod_name)
        checkpoint_file_path = os.path.join(checkpoint_dir, f"{checkpoint_name}.tar")
        print(f"Inspecting checkpoint: {checkpoint_name}")
        # Run the `checkpointctl` command
        await send_progress(username, {"progress": 70, "task_name": "Inspecting Checkpoint", "message": f"Running command checkpointctl inspect {checkpoint_file_path} --all --format json"})
        
        try:
            # Try multiple checkpointctl approaches to handle different failure modes
            inspect_output = None
            
            # Approach 1: Basic inspect without --all flag
            try:
                print("SnapAPI: Trying checkpointctl inspect without --all flag...")
                inspect_output = await run(['checkpointctl', 'inspect', checkpoint_file_path, '--format', 'json'], True, True, True)
            except Exception as first_error:
                print(f"SnapAPI: First checkpointctl attempt failed: {str(first_error)}")
                
                # Approach 2: Try with --all flag
                try:
                    print("SnapAPI: Trying checkpointctl inspect with --all flag...")
                    inspect_output = await run(['checkpointctl', 'inspect', checkpoint_file_path, '--all', '--format', 'json'], True, True, True)
                except Exception as second_error:
                    print(f"SnapAPI: Second checkpointctl attempt failed: {str(second_error)}")
                    
                    # Approach 3: Try without JSON format (raw output)
                    try:
                        print("SnapAPI: Trying checkpointctl inspect without JSON format...")
                        inspect_output = await run(['checkpointctl', 'inspect', checkpoint_file_path], True, True, True)
                        # Convert raw output to JSON-like format
                        raw_output = inspect_output.stdout
                        json_output = f'{{"raw_inspect_output": "{raw_output.replace(chr(34), chr(92)+chr(34))}"}}'
                        inspect_output.stdout = json_output
                    except Exception as third_error:
                        print(f"SnapAPI: All checkpointctl attempts failed: {str(third_error)}")
                        raise third_error
            
            # Save the output in the same folder as the checkpoint file with a different name to avoid conflicts
            # Use "_inspect" suffix to distinguish from metadata JSON files
            output_file_path = os.path.join(checkpoint_dir, f"{checkpoint_name}_inspect.json")
            with open(output_file_path, 'w') as file:
                file.write(inspect_output.stdout)
                
        except Exception as checkpointctl_error:
            # Handle checkpointctl specific errors (like environment variable parsing issues)
            error_msg = f"Checkpointctl inspect failed: {str(checkpointctl_error)}"
            await send_progress(username, {"progress": "failed", "task_name": "Inspecting Checkpoint", "message": error_msg})
            raise HTTPException(status_code=500, detail=error_msg)

        # Get the insights
        # CheckpointInsightsresponse = await CheckpointInsightsUseCase(CheckpointInsightsRequest(checkpoint_info_path=output_file_path, openai_api_key_secret_name="openai-api-key"))
        await send_progress(username, {"progress": 100, "task_name": "Inspecting Checkpoint", "message": f"Finished inspecting checkpoint, output: {output_file_path}"})
        return {"output": output_file_path}
        # return {"output": output_file_path, "insights": CheckpointInsightsresponse.insights}
    except Exception as e:
        await send_progress(username, {"progress": "failed", "task_name": "Inspecting Checkpoint", "message": f"Failed with error: {str(e)}"})
        logger.error(f"SnapAPI: Failed to run checkpointctl: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to run checkpointctl: {str(e)}")

@router.get("/checkpointctl/information")
async def checkpointctl_information(params: CheckpointctlRequest = Depends(), username: str = Depends(verify_token)):
    pod_name = params.pod_name  # Assuming pod_id is provided in the request
    checkpoint_name = params.checkpoint_name
    checkpoint_dir = os.path.join(checkpoint_path, pod_name)  # Include pod_id in the directory path
    # Look for the inspect output file with _inspect suffix
    checkpoint_file_path = os.path.join(checkpoint_dir, f"{checkpoint_name}_inspect.json")
    # Check if the checkpoint inspect file exists
    if not os.path.exists(checkpoint_file_path):
        raise HTTPException(
            status_code=404, 
            detail=f"Checkpoint inspect file not found: {checkpoint_file_path}. Please run analysis first using the checkpointctl endpoint."
        )
    try:
        with open(checkpoint_file_path, 'r') as file:
            content = json.load(file)  # Parse JSON content from the file
            return {"logs": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.post("/analyze/volatility")
async def analyze_volatility(request: VolatilityRequest):
    return await analyze_checkpoint_volatility(request)

@router.get("/analyze/volatility/results")
async def return_checkpoint_volatility_analysis(params: VolatilityRequest = Depends()):
    pod_name = params.pod_name  # Assuming pod_id is provided in the request
    checkpoint_name = params.checkpoint_name
    request = VolatilityRequest(pod_name=pod_name, checkpoint_name=checkpoint_name)
    return await checkpoint_volatility_analysis(request)
