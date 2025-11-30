from pydantic import BaseModel
from classes.clusterconfig import ClusterConfig, ClusterConfigDetails
import os
import json
import logging
from flows.config.clusters.create_cluster_config import ClusterConfigRequest
from typing import List

logger = logging.getLogger("automation_api")

class ClusterConfigResponse(BaseModel):
    success: bool
    message: str
    cluster_configs: List[ClusterConfig]

async def list_cluster_config():
    # get all the cluster configs from the config folder in the cluster config directory
    # Resolve path relative to the app's base directory (src/)
    # File is at: src/flows/config/clusters/list_cluster_config.py
    # Need to go up 4 levels to get to src/
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    path = os.path.join(BASE_DIR, "config", "clusters")
    cluster_configs = []
    
    logger.info(f"[ClusterConfig] Looking for cluster configs in: {path}")
    
    # Check if the directory exists
    if not os.path.exists(path):
        logger.warning(f"[ClusterConfig] Cluster config directory {path} does not exist")
        return ClusterConfigResponse(
            success=True,
            message="No cluster configs found - directory does not exist",
            cluster_configs=cluster_configs
        )
    
    try:
        files_found = os.listdir(path)
        logger.info(f"[ClusterConfig] Found {len(files_found)} files in {path}")
        
        for file in files_found:
            if file.endswith(".json"):
                file_path = os.path.join(path, file)
                logger.info(f"[ClusterConfig] Attempting to load: {file_path}")
                #Read the json file
                with open(file_path, "r") as f:
                    try:
                        data = json.load(f)
                        cluster_details_data = data["cluster_config_details"]
                        
                        # Create ClusterConfigDetails using model_construct to bypass all validation
                        cluster_details = ClusterConfigDetails.model_construct(
                            kube_api_url=cluster_details_data["kube_api_url"],
                            token=cluster_details_data.get("token", cluster_details_data.get("kube_password", ""))
                        )
                        
                        # Create ClusterConfig with the details
                        config = ClusterConfig(
                            cluster_config_details=cluster_details,
                            name=data["name"]
                        )
                        cluster_configs.append(config)
                        logger.info(f"[ClusterConfig] Successfully loaded cluster config: {data['name']}")
                    except Exception as e:
                        logger.error(f"[ClusterConfig] Error loading cluster config file {file}: {e}")
    except Exception as e:
        logger.error(f"[ClusterConfig] Error accessing cluster config directory {path}: {e}")

    logger.info(f"[ClusterConfig] Total cluster configs loaded: {len(cluster_configs)}")
    return ClusterConfigResponse(
        success=True,
        message="Cluster configs listed successfully",
        cluster_configs=cluster_configs
    )
