import os
import json
import logging
from datetime import datetime
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
    return await checkpoint_and_push_from_pod_spec(
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
                            checkpoint_name = container.replace('.tar', '')
                            
                            # Check for analysis results (_inspect.json contains the actual analysis)
                            analysis_result = f"{checkpoint_name}_inspect.json"
                            analysis_result_path = os.path.join(pod_path, analysis_result)
                            
                            # Check for metadata file (.json contains metadata for image creation)
                            metadata_result = f"{checkpoint_name}.json"
                            metadata_result_path = os.path.join(pod_path, metadata_result)
                            
                            # Check for volatility analysis
                            volatility_analysis_file = os.path.join(pod_path, f"{checkpoint_name}_volatility_analysis.txt")
                            
                            # Determine which analysis file exists (prioritize _inspect.json for analysis)
                            has_analysis = os.path.exists(analysis_result_path)
                            analysis_file = analysis_result if has_analysis else None
                            
                            pod_container_mapping.append({
                                "pod_name": pod,
                                "checkpoint_name": container,
                                "analysis_result": analysis_file if has_analysis else None,
                                "scan_result": os.path.exists(volatility_analysis_file),
                                "has_analysis": has_analysis
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

async def run_checkpointctl_fallback(checkpoint_file_path: str, username: str, error_message: str):
    """
    Dynamic fallback method for checkpointctl inspection when specific flags fail.
    Detects which flag is problematic and runs all other flags individually.
    """
    try:
        await send_progress(username, {"progress": 65, "task_name": "Inspecting Checkpoint", "message": f"Running dynamic fallback inspection"})
        
        # Define all available checkpointctl inspect flags (excluding --all, --format, --help which are handled separately)
        # Note: --pid requires a PID parameter, so we'll handle it separately
        # Other checkpointctl commands available: build, list, memparse, show
        all_flags = [
            '--files',           # Display open file descriptors
            '--metadata',        # Show metadata
            '--mounts',          # Display mounts overview
            '--ps-tree',         # Display process tree
            '--ps-tree-cmd',     # Display process tree with command line arguments
            '--ps-tree-env',     # Display process tree with environment variables
            '--sockets',         # Display open sockets
            '--stats'            # Display checkpoint statistics
        ]
        
        # Special flags that require parameters
        special_flags = {
            '--pid': '1'  # Default to PID 1 (main process)
        }
        
        # Detect problematic flag from error message
        problematic_flag = None
        
        # Try to detect the specific flag that's causing issues
        for flag in all_flags:
            flag_name = flag.replace('--', '').replace('-', ' ')
            # Check if the flag name appears in the error message
            if flag_name in error_message.lower() or flag.replace('--', '') in error_message.lower():
                problematic_flag = flag
                break
        
        # Additional specific checks for common error patterns
        if not problematic_flag:
            if 'environment variable' in error_message.lower():
                problematic_flag = '--ps-tree-env'
            elif 'process tree' in error_message.lower():
                problematic_flag = '--ps-tree'
            elif 'file descriptor' in error_message.lower():
                problematic_flag = '--files'
            elif 'socket' in error_message.lower():
                problematic_flag = '--sockets'
        
        # If we still can't detect the specific flag, exclude --ps-tree-env as default
        if not problematic_flag:
            problematic_flag = '--ps-tree-env'
            logger.warning(f"SnapAPI: Could not detect specific problematic flag, defaulting to exclude {problematic_flag}")
        
        logger.info(f"SnapAPI: Detected problematic flag: {problematic_flag}, excluding from inspection")
        
        # Get list of flags to run (exclude the problematic one)
        flags_to_run = [flag for flag in all_flags if flag != problematic_flag]
        
        await send_progress(username, {"progress": 70, "task_name": "Inspecting Checkpoint", "message": f"Running inspection with {len(flags_to_run)} flags (excluding {problematic_flag})"})
        
        # Collect all inspection results
        inspection_results = []
        
        # First, get basic checkpoint information (no flags)
        await send_progress(username, {"progress": 75, "task_name": "Inspecting Checkpoint", "message": f"Getting basic checkpoint information"})
        basic_output = await run(['checkpointctl', 'inspect', checkpoint_file_path, '--format', 'json'], True, True, True)
        basic_data = json.loads(basic_output.stdout)
        inspection_results.extend(basic_data)
        
        # Run each flag individually and merge results
        total_flags = len(flags_to_run)
        for i, flag in enumerate(flags_to_run):
            try:
                progress = 75 + int((i + 1) * 20 / total_flags)
                flag_name = flag.replace('--', '').replace('-', ' ').title()
                await send_progress(username, {"progress": progress, "task_name": "Inspecting Checkpoint", "message": f"Getting {flag_name} information"})
                
                # Build command with special handling for flags that require parameters
                cmd = ['checkpointctl', 'inspect', checkpoint_file_path, flag, '--format', 'json']
                if flag in special_flags:
                    cmd.insert(-2, special_flags[flag])  # Insert parameter before --format
                
                flag_output = await run(cmd, True, True, True)
                flag_data = json.loads(flag_output.stdout)
                
                # Merge the flag data into the main result
                if flag_data and len(flag_data) > 0 and inspection_results:
                    inspection_results[0].update(flag_data[0])
                    
            except Exception as flag_error:
                logger.warning(f"SnapAPI: Flag {flag} also failed: {str(flag_error)}")
                # Continue with other flags even if one fails
        
        # Add metadata about the fallback method
        if inspection_results and len(inspection_results) > 0:
            inspection_results[0]['fallback_note'] = {
                'message': f'Some inspection data could not be displayed due to parsing error',
                'excluded_flag': problematic_flag,
                'reason': 'Detected problematic flag from error message',
                'method': 'dynamic_fallback_inspection',
                'flags_executed': flags_to_run,
                'original_error': error_message
            }
        
        await send_progress(username, {"progress": 98, "task_name": "Inspecting Checkpoint", "message": f"Dynamic fallback inspection completed successfully"})
        
        # Create a mock output object similar to what run() returns
        class MockOutput:
            def __init__(self, stdout_data):
                self.stdout = stdout_data
        
        return MockOutput(json.dumps(inspection_results, indent=2))
        
    except Exception as e:
        logger.error(f"SnapAPI: Dynamic fallback checkpointctl inspection failed: {str(e)}")
        raise e

@router.post("/checkpointctl")
async def checkpointctl(request: CheckpointctlRequest, username: str = Depends(verify_token)):
    try:
        await send_progress(username, {"progress": 35, "task_name": "Inspecting Checkpoint", "message": f"Inspecting checkpoint initiated"})
        pod_name = request.pod_name
        checkpoint_name = request.checkpoint_name
        checkpoint_dir = os.path.join(checkpoint_path, pod_name)
        checkpoint_file_path = os.path.join(checkpoint_dir, f"{checkpoint_name}.tar")
        print(f"Inspecting checkpoint: {checkpoint_name}")
        
        # Try full inspection first
        await send_progress(username, {"progress": 50, "task_name": "Inspecting Checkpoint", "message": f"Attempting full checkpoint inspection"})
        try:
            inspect_output = await run(['checkpointctl', 'inspect', checkpoint_file_path, '--all', '--format', 'json'], True, True, True)
            await send_progress(username, {"progress": 100, "task_name": "Inspecting Checkpoint", "message": f"Full inspection completed successfully"})
        except Exception as e:
            error_message = str(e)
            # Check if the error is related to checkpointctl parsing issues
            if any(keyword in error_message.lower() for keyword in ['invalid environment variable', 'failed to build json', 'failed to get process tree']):
                await send_progress(username, {"progress": 60, "task_name": "Inspecting Checkpoint", "message": f"Detected checkpointctl parsing error. Using dynamic fallback inspection method"})
                logger.warning(f"SnapAPI: Checkpointctl parsing error detected, using dynamic fallback method: {error_message}")
                
                # Use dynamic fallback method
                inspect_output = await run_checkpointctl_fallback(checkpoint_file_path, username, error_message)
            else:
                # Re-raise if it's a different error
                raise e

        # Save the output in the same folder as the checkpoint file with _inspect suffix for analysis results
        output_file_path = os.path.join(checkpoint_dir, f"{checkpoint_name}_inspect.json")
        with open(output_file_path, 'w') as file:
            file.write(inspect_output.stdout)

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
    pod_name = params.pod_name
    checkpoint_name = params.checkpoint_name
    checkpoint_dir = os.path.join(checkpoint_path, pod_name)
    
    # Look for the analysis results file (_inspect.json) - this is for analysis results
    analysis_file_path = os.path.join(checkpoint_dir, f"{checkpoint_name}_inspect.json")
    
    logger.info(f"Looking for analysis results file: {analysis_file_path}")
    
    # Check if the analysis results file exists
    if not os.path.exists(analysis_file_path):
        # Fallback to the regular .json file if _inspect.json doesn't exist
        fallback_file_path = os.path.join(checkpoint_dir, f"{checkpoint_name}.json")
        if os.path.exists(fallback_file_path):
            analysis_file_path = fallback_file_path
            logger.info(f"Using fallback analysis file: {fallback_file_path}")
        else:
            error_msg = f"Analysis results file not found: {analysis_file_path}. Please run analysis first using the checkpointctl endpoint."
            logger.error(error_msg)
            raise HTTPException(status_code=404, detail=error_msg)
    
    try:
        with open(analysis_file_path, 'r') as file:
            content = json.load(file)  # Parse JSON content from the file
            logger.info(f"Successfully loaded analysis data from: {analysis_file_path}")
            return {"logs": content}
    except json.JSONDecodeError as json_error:
        error_msg = f"Failed to parse JSON from analysis file: {str(json_error)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = f"Unexpected error reading analysis file: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/analyze/volatility")
async def analyze_volatility(request: VolatilityRequest):
    return await analyze_checkpoint_volatility(request)

@router.get("/analyze/volatility/results")
async def return_checkpoint_volatility_analysis(params: VolatilityRequest = Depends()):
    pod_name = params.pod_name  # Assuming pod_id is provided in the request
    checkpoint_name = params.checkpoint_name
    request = VolatilityRequest(pod_name=pod_name, checkpoint_name=checkpoint_name)
    return await checkpoint_volatility_analysis(request)
