from pydantic import BaseModel, validator
from classes.clusterconfig import ClusterConfig, ClusterConfigDetails
from classes.cluster_cache_models import ClusterCacheRequest, ClusterCache
from flows.config.clusterCache.create_cluster_cache import create_cluster_cache
import os
import json
from typing import Optional, Literal
import re

class ClusterConfigRequest(BaseModel):
    kube_api_url: str
    kube_username: Optional[str] = None
    kube_password: str
    nodes_username: str
    name: str
    auth_method: Literal["username_password", "token"] = "username_password"
    registry: Optional[str] = None  # Registry name for cluster cache
    repo: Optional[str] = "snap_images"  # Repository name for cluster cache
    
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

async def create_cluster_config(request: ClusterConfigRequest):

    # TODO: Implement the logic to create the cluster config
    # check if the config file exists under the config folder within the config directory
    # if it does, return an error
    path = f"config/clusters/{request.name}.json"
    if os.path.exists(path):
        return ClusterConfigResponse(
            success=False,
            message=f"Cluster config file {request.name} already exists"
        )

    config = ClusterConfig(    
        cluster_config_details=ClusterConfigDetails(
            kube_api_url=request.kube_api_url,
            kube_username=request.kube_username,
            kube_password=request.kube_password,
            nodes_username=request.nodes_username,
            auth_method=request.auth_method
        ),
        name=request.name
    )
    # if it doesn't, create the config
    # save the config to the config folder in the config file
    with open(path, "w") as f:
        json.dump(config.to_dict(), f, indent=4)

    # Automatically create cluster cache if registry is provided
    if request.registry:
        try:
            cluster_cache_request = ClusterCacheRequest(
                cluster=request.name,
                registry=request.registry,
                repo=request.repo
            )
            cluster_cache_result = await create_cluster_cache(cluster_cache_request)
            
            if cluster_cache_result.success:
                return ClusterConfigResponse(
                    success=True,
                    message=f"Cluster config file {request.name} and cluster cache created successfully"
                )
            else:
                # Cluster config was created but cluster cache failed
                return ClusterConfigResponse(
                    success=False,
                    message=f"Cluster config file {request.name} created but cluster cache creation failed: {cluster_cache_result.message}"
                )
        except Exception as e:
            # Cluster config was created but cluster cache failed
            return ClusterConfigResponse(
                success=False,
                message=f"Cluster config file {request.name} created but cluster cache creation failed: {str(e)}"
            )
    else:
        return ClusterConfigResponse(
            success=True,
            message=f"Cluster config file {request.name} created successfully (no cluster cache created - registry not specified)"
        )
