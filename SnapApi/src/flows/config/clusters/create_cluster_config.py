from pydantic import BaseModel, validator
from classes.clusterconfig import ClusterConfig, ClusterConfigDetails
from classes.cluster_cache_models import ClusterCacheRequest, ClusterCache
from flows.config.clusterCache.create_cluster_cache import create_cluster_cache
from flows.cluster_status.check_cluster_status import check_cluster_status
import os
import json
from typing import Optional
import re

class ClusterConfigRequest(BaseModel):
    kube_api_url: str
    token: str
    name: str
    registry: Optional[str] = None  # Registry name for cluster cache
    repo: Optional[str] = "snap_images"  # Repository name for cluster cache
    
    @validator('token')
    def validate_token(cls, v):
        if not v or not v.strip():
            raise ValueError('Token is required')
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
            token=request.token
        ),
        name=request.name
    )
    # if it doesn't, create the config
    # save the config to the config folder in the config file
    with open(path, "w") as f:
        json.dump(config.to_dict(), f, indent=4)

    # Automatically create cluster cache if registry is provided
    cluster_cache_success = True
    cluster_cache_message = ""
    if request.registry:
        try:
            cluster_cache_request = ClusterCacheRequest(
                cluster=request.name,
                registry=request.registry,
                repo=request.repo
            )
            cluster_cache_result = await create_cluster_cache(cluster_cache_request)
            
            if not cluster_cache_result.success:
                cluster_cache_success = False
                cluster_cache_message = f"Cluster cache creation failed: {cluster_cache_result.message}"
        except Exception as e:
            cluster_cache_success = False
            cluster_cache_message = f"Cluster cache creation failed: {str(e)}"
    
    # Run cluster status check after creating cluster
    check_result = await check_cluster_status(request.name)
    check_message = check_result.get("message", "")
    
    # Build response message
    messages = [f"Cluster config file {request.name} created successfully"]
    if request.registry:
        if cluster_cache_success:
            messages.append("Cluster cache created successfully")
        else:
            messages.append(cluster_cache_message)
    else:
        messages.append("No cluster cache created - registry not specified")
    
    if check_result.get("success"):
        messages.append("Cluster status check completed")
    else:
        messages.append(f"Cluster status check failed: {check_message}")
    
    return ClusterConfigResponse(
        success=True,
        message=". ".join(messages)
    )
