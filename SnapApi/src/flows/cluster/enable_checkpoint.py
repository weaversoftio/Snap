from pydantic import BaseModel
import os
from fastapi import HTTPException
import asyncio
import re
from typing import List, Dict, Any
from routes.websocket import send_progress

SNAP_API_URL = os.getenv("SNAP_API_URL", "http://snapapi.apps-crc.testing")

class ClusterRequest(BaseModel):
    clusterType: str
    clusterName: str

class EnableCheckPointResponse(BaseModel):
    success: bool
    message: str
    details: Dict[str, List[Dict[str, str]]] = {}
    output: str  # Includes Ansible logs

task_progress = {
    "Initiated": 25,
    "ClusterType": 50,
    "AnsiblePlaybook": 75,
    "Completed": 100,
    "Failed": "failed"
}
async def enable_checkpointing(request: ClusterRequest, username: str):
    """
    Enables container checkpointing in an OpenShift or Kubernetes cluster.
    """
    fastapi_host = SNAP_API_URL
    await send_progress(username, {"progress": task_progress["Initiated"], "task_name": "Enabling Checkpointing", "message": f"Enabling checkpointing initiated with clusterName: {request.clusterName}"})
    try:
        if request.clusterType.lower() == "kubernetes":
            await send_progress(username, {"progress": task_progress["ClusterType"], "task_name": "Enabling Checkpointing", "message": f"Cluster type: Kubernetes"})
            inventory_file = os.path.join('config', 'nodeStore', f'{request.clusterName}', f'{request.clusterName}.json')
            playbook_path = os.path.join('playbook', 'EnableCheckpointingK8s.yaml')

            if not os.path.exists(playbook_path):
                raise HTTPException(status_code=500, detail=f"Playbook '{playbook_path}' not found.")

            if not os.path.exists(inventory_file):
                raise HTTPException(status_code=500, detail=f"Inventory file '{inventory_file}' not found.")
            
            def set_ansible_private_key_env(cluster):
                key_path = f"/app/config/nodeStore/{cluster}/{cluster}"
                os.environ["ANSIBLE_PRIVATE_KEY_FILE"] = key_path
                os.environ["ANSIBLE_HOST_KEY_CHECKING"] = "False"
                print(f"ANSIBLE_PRIVATE_KEY_FILE set to {key_path} for this session.")
            
            set_ansible_private_key_env(request.clusterName)
            try:
                await send_progress(username, {"progress": task_progress["AnsiblePlaybook"], "task_name": "Enabling Checkpointing", "message": f"Running Ansible Playbook"})
                # Run the Ansible playbook
                print(f"Running: ansible-playbook -i {inventory_file} {playbook_path}")
                process = await asyncio.create_subprocess_exec(
                    "ansible-playbook", "-i", inventory_file, playbook_path,"--extra-vars", f"fastapi_host={fastapi_host}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()

                # Decode byte streams
                stdout = stdout.decode()
                stderr = stderr.decode()
                oc_error_message = "error: Missing or incomplete configuration info."
                if oc_error_message in stderr or oc_error_message in stdout:
                    message = "Can't access to the cluster. Ensure system is logged in correctly to cluster"
                    await send_progress(username, {"progress": task_progress["Failed"], "task_name": "Enabling Checkpointing", "message": message})
                    return EnableCheckPointResponse(
                        success=False,
                        message=message,
                        details={},
                        output=stdout
                    )

                if process.returncode != 0:
                    # Parse the stdout to extract failed tasks and their error messages
                    failed_tasks = []
                    task_name_pattern = re.compile(r'TASK \[(.*?)\]')
                    error_pattern = re.compile(r'^(fatal: \[.*?\]): (.*?)$', re.MULTILINE)
                    current_task = None

                    for line in stdout.splitlines():
                        task_match = task_name_pattern.search(line)
                        if task_match:
                            current_task = task_match.group(1)
                        error_match = error_pattern.search(line)
                        if error_match and current_task:
                            failed_tasks.append({
                                "task": current_task,
                                "error": error_match.group(2)
                            })
                            current_task = None

                    if not failed_tasks:
                        detail = f"Playbook execution failed with return code {process.returncode}. Error details: {stderr.strip() or 'No error details available.'}"
                        await send_progress(username, {"progress": task_progress["Failed"], "task_name": "Enabling Checkpointing", "message": detail})
                        # If no specific failed tasks were found, provide general stderr output
                        raise HTTPException(
                            status_code=500,
                            detail=detail
                        )

                    await send_progress(username, {"progress": task_progress["Failed"], "task_name": "Enabling Checkpointing", "message": f"Issues found, failed tasks: {failed_tasks}"})
                    return EnableCheckPointResponse(
                        success=False,
                        message="Issues found",
                        details={"failed_tasks": failed_tasks},  # Corrected structure
                        output=stdout
                    )

                message="Cluster Enable Checkpoint successful"
                await send_progress(username, {"progress": task_progress["Completed"], "task_name": "Enabling Checkpointing", "message": message})
                return EnableCheckPointResponse(
                    success=True,
                    message=message,
                    details={},
                    output=stdout
                )

            except Exception as e:
                detail=f"An error occurred: {str(e)}"
                await send_progress(username, {"task_name": "Enabling Checkpointing", "message": detail})
                raise HTTPException(status_code=500, detail=detail)

        elif request.clusterType.lower() == "openshift":
            await send_progress(username, {"progress": task_progress["ClusterType"], "task_name": "Enabling Checkpointing", "message": f"Enabling checkpointing initiated \n ClusterName: {request.clusterName} \nCluster type: Openshift"})
            inventory_file = os.path.join('config', 'nodeStore', f'{request.clusterName}', f'{request.clusterName}.json')
            playbook_path = os.path.join('playbook', 'EnableCheckpointingOpenshift.yaml')

            if not os.path.exists(playbook_path):
                raise HTTPException(status_code=500, detail=f"Playbook '{playbook_path}' not found.")

            if not os.path.exists(inventory_file):
                raise HTTPException(status_code=500, detail=f"Inventory file '{inventory_file}' not found.")
            
            def set_ansible_private_key_env(cluster):
                key_path = f"/app/config/nodeStore/{cluster}/{cluster}"
                os.environ["ANSIBLE_PRIVATE_KEY_FILE"] = key_path
                print(f"ANSIBLE_PRIVATE_KEY_FILE set to {key_path} for this session.")
            
            set_ansible_private_key_env(request.clusterName)
            try:
                await send_progress(username, {"progress": task_progress["AnsiblePlaybook"], "task_name": "Enabling Checkpointing", "message": f"Running ansible playbook command"})
                # Run the Ansible playbook
                print(f"Running: ansible-playbook -i {inventory_file} {playbook_path}")
                process = await asyncio.create_subprocess_exec(
                    "ansible-playbook", "-i", inventory_file, playbook_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()

                # Decode byte streams
                stdout = stdout.decode()
                stderr = stderr.decode()
                oc_error_message = "error: Missing or incomplete configuration info."
                if oc_error_message in stderr or oc_error_message in stdout:
                    message = "Can't access to the cluster. Ensure system is logged in correctly to cluster"
                    await send_progress(username, {"progress": task_progress["Failed"], "task_name": "Enabling Checkpointing", "message": message})
                    return EnableCheckPointResponse(
                        success=False,
                        message=message,
                        details={},
                        output=stdout
                    )

                if process.returncode != 0:
                    # Parse the stdout to extract failed tasks and their error messages
                    failed_tasks = []
                    task_name_pattern = re.compile(r'TASK \[(.*?)\]')
                    error_pattern = re.compile(r'^(fatal: \[.*?\]): (.*?)$', re.MULTILINE)
                    current_task = None

                    for line in stdout.splitlines():
                        task_match = task_name_pattern.search(line)
                        if task_match:
                            current_task = task_match.group(1)
                        error_match = error_pattern.search(line)
                        if error_match and current_task:
                            failed_tasks.append({
                                "task": current_task,
                                "error": error_match.group(2)
                            })
                            current_task = None

                    if not failed_tasks:
                        detail = f"Playbook execution failed with return code {process.returncode}. Error details: {stderr.strip() or 'No error details available.'}"
                        await send_progress(username, {"progress": task_progress["Failed"], "task_name": "Enabling Checkpointing", "message": detail})
                        # If no specific failed tasks were found, provide general stderr output
                        raise HTTPException(
                            status_code=500,
                            detail=detail
                        )

                    await send_progress(username, {"progress": task_progress["Failed"], "task_name": "Enabling Checkpointing", "message": f"Issues found, failed tasks: {failed_tasks}"})
                    return EnableCheckPointResponse(
                        success=False,
                        message="Issues found",
                        details={"failed_tasks": failed_tasks},  # Corrected structure
                        output=stdout
                    )

                message="Cluster Enable Checkpoint successful"
                await send_progress(username, {"progress": task_progress["Completed"], "task_name": "Enabling Checkpointing", "message": message})
                return EnableCheckPointResponse(
                    success=True,
                    message=message,
                    details={},
                    output=stdout
                )

            except Exception as e:
                detail=f"An error occurred: {str(e)}"
                await send_progress(username, {"progress": task_progress["Failed"], "task_name": "Enabling Checkpointing", "message": detail})
                raise HTTPException(status_code=500, detail=detail)

        else:
            detail="Invalid clusterType. Must be 'kubernetes' or 'openshift'."
            await send_progress(username, {"progress": task_progress["Failed"], "task_name": "Enabling Checkpointing", "message": detail})
            raise HTTPException(status_code=400, detail=detail)
    except Exception as e:
        detail=f"An error occurred: {str(e)}"
        await send_progress(username, {"progress": task_progress["Failed"], "task_name": "Enabling Checkpointing", "message": detail})
        raise HTTPException(status_code=500, detail=detail)
