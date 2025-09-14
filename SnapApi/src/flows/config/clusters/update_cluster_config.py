from pydantic import BaseModel, validator
from classes.clusterconfig import ClusterConfig, ClusterConfigDetails
import os
import json

class ClusterConfigRequest(BaseModel):
    kube_api_url: str
    token: str
    name: str
    
    @validator('token')
    def validate_token(cls, v):
        if not v or not v.strip():
            raise ValueError('Token is required')
        return v

class ClusterConfigResponse(BaseModel):
    success: bool
    message: str

async def update_cluster_config(request: ClusterConfigRequest):
    try:
        path = f"config/clusters/{request.name}.json"
        
        # Check if config file exists
        if not os.path.exists(path):
            return ClusterConfigResponse(
                success=False,
                message=f"Cluster config file {request.name} does not exist"
            )

        # Create a new config with existing values
        config_details = ClusterConfigDetails(
            kube_api_url=request.kube_api_url,
            token=request.token
        )

        # Create new config object
        config = ClusterConfig(
            cluster_config_details=config_details,
            name=request.name
        )

        # Save updated config
        with open(path, "w") as f:
            json.dump(config.to_dict(), f, indent=4)

        return ClusterConfigResponse(
            success=True,
            message=f"Cluster config file {request.name} updated successfully"
        )

    except Exception as e:
        return ClusterConfigResponse(
            success=False,
            message=f"Error updating cluster config: {str(e)}"
        )
