from pydantic import BaseModel, validator
from classes.clusterconfig import ClusterConfig, ClusterConfigDetails
import os
import json
from typing import Optional, Literal

class ClusterConfigRequest(BaseModel):
    kube_api_url: str
    kube_username: Optional[str] = None
    kube_password: str
    nodes_username: str
    name: str
    auth_method: Literal["username_password", "token"] = "username_password"
    
    @validator('kube_username')
    def validate_username_for_auth_method(cls, v, values):
        auth_method = values.get('auth_method', 'username_password')
        if auth_method == 'username_password' and not v:
            raise ValueError('Username is required for username_password authentication')
        elif auth_method == 'token' and v:
            # Clear username for token auth
            return None
        return v
    
    @validator('kube_password')
    def validate_password_or_token(cls, v, values):
        if not v or not v.strip():
            auth_method = values.get('auth_method', 'username_password')
            field_name = 'Token' if auth_method == 'token' else 'Password'
            raise ValueError(f'{field_name} is required')
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
            kube_username=request.kube_username,
            kube_password=request.kube_password,
            nodes_username=request.nodes_username,
            auth_method=request.auth_method
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
