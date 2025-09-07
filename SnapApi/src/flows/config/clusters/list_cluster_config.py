from pydantic import BaseModel
from classes.clusterconfig import ClusterConfig, ClusterConfigDetails
import os
import json
from flows.config.clusters.create_cluster_config import ClusterConfigRequest
from typing import List

class ClusterConfigResponse(BaseModel):
    success: bool
    message: str
    cluster_configs: List[ClusterConfig]

async def list_cluster_config():
    # get all the cluster configs from the config folder in the cluster config directory
    path = f"config/clusters"
    cluster_configs = []
    
    # Check if the directory exists
    if not os.path.exists(path):
        print(f"Cluster config directory {path} does not exist")
        return ClusterConfigResponse(
            success=True,
            message="No cluster configs found - directory does not exist",
            cluster_configs=cluster_configs
        )
    
    try:
        for file in os.listdir(path):
            if file.endswith(".json"):
                #Read the json file
                with open(os.path.join(path, file), "r") as f:
                    try:
                        data = json.load(f)
                        cluster_details_data = data["cluster_config_details"]
                        
                        # Handle backward compatibility - if auth_method is not present, determine it based on username
                        auth_method = cluster_details_data.get("auth_method")
                        if auth_method is None:
                            # Backward compatibility: determine auth method based on username presence
                            auth_method = "token" if not cluster_details_data.get("kube_username") else "username_password"
                        
                        # Create ClusterConfigDetails using model_construct to bypass all validation
                        cluster_details = ClusterConfigDetails.model_construct(
                            kube_api_url=cluster_details_data["kube_api_url"],
                            kube_username=cluster_details_data.get("kube_username"),
                            kube_password=cluster_details_data["kube_password"],
                            nodes_username=cluster_details_data["nodes_username"],
                            auth_method=auth_method
                        )
                        
                        # Create ClusterConfig with the details
                        config = ClusterConfig(
                            cluster_config_details=cluster_details,
                            name=data["name"]
                        )
                        cluster_configs.append(config)
                        print(f"Successfully loaded cluster config: {data['name']}")
                    except Exception as e:
                        print(f"Error loading cluster config file {file}: {e}")
    except Exception as e:
        print(f"Error accessing cluster config directory {path}: {e}")

    return ClusterConfigResponse(
        success=True,
        message="Cluster configs listed successfully",
        cluster_configs=cluster_configs
    )
