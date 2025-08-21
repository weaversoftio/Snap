from flows.proccess_utils import run
from fastapi import Depends, HTTPException
import os
from classes.clusterconfig import ClusterConfig
import base64
from routes.websocket import send_progress
from middleware.verify_token import verify_token

# This function is used to login to a kubernetes cluster using kubectl with the given credentials   
async def kubectl_cluster_login(cluster_config_name: str, username: str):
    try:
        # Get the cluster config details from the config folder
        path = f"config/clusters/{cluster_config_name}.json"
        #check if the file exists
        if not os.path.exists(path):
            message="Cluster config not found"
            await send_progress(username, {"progress": "failed","task_name": "Cluster Login", "message": message})
            return {"success": False, "message": message}
        
        try:
            with open(path, "r") as f:
                cluster_config = ClusterConfig.model_validate_json(f.read())
        except Exception as e:
            message=f"Error validating cluster config: {str(e)}"
            await send_progress(username, {"progress": "failed","task_name": "Cluster Login", "message": message})
            return {"success": False, "message": message}
        
        # Run oc login with the given credentials
        kube_api_url = cluster_config.cluster_config_details.kube_api_url
        kube_username = cluster_config.cluster_config_details.kube_username
        kube_password = cluster_config.cluster_config_details.kube_password
        # ssh_key = base64.b64decode(cluster_config.cluster_config_details.ssh_key).decode()
        message=f"Logging in to the kubernetes cluster"
        await send_progress(username, {"progress": 16, "task_name": "Cluster Login", "message": message})
        print(f"Logging in to the kubernetes cluster with the given credentials: {kube_api_url}, {kube_username}, {kube_password}")
        # await run(["oc", "login", kube_api_url, "--token", ssh_key, "--insecure-skip-tls-verify=true"])
        if kube_username == "":
            # Use token-based login
            await run([
                "oc", "login", kube_api_url,
                "--token", kube_password,
                "--insecure-skip-tls-verify=true"
            ])
        else:
            # Use username/password-based login
            await run([
                "oc", "login", kube_api_url,
                "--username", kube_username,
                "--password", kube_password,
                "--insecure-skip-tls-verify=true"
            ])
        await send_progress(username, {"progress": 32, "task_name": "Cluster Login", "message": "Successfully logged in to the kubernetes cluster"})
        print("Logged in to the kubernetes cluster")

        # Get the current context   
        await send_progress(username, {"progress": 48, "task_name": "Cluster Login", "message": "Getting the current context"})
        context = (await run(["oc", "config", "current-context"])).stdout.strip()
        print(f"Current context: {context}")
        await send_progress(username, {"progress": 64, "task_name": "Cluster Login", "message": f"Current context: {context}"})

        # Get the current user
        await send_progress(username, {"progress": 80, "task_name": "Cluster Login", "message": f"Getting the current user"})
        user = (await run(["oc", "whoami"])).stdout.strip()
        print(f"Current user: {user}")

        await send_progress(username, {"progress": 100, "task_name": "Cluster Login", "message": f"Current user: {user}\nLogged in to the kubernetes cluster"})
        return {"success": True, "message": "Logged in to the kubernetes cluster"}
    except Exception as e:
        await send_progress(username, {"progress": "failed", "task_name": "Cluster Login", "message": f"Unexpected error: {str(e)}"})
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )
