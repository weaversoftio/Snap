import os
import json
from classes.cluster_cache_models import ClusterCacheRequest, ClusterCacheResponse, ClusterCache, ClusterCacheDetails

async def update_cluster_cache(request: ClusterCacheRequest):
    """Update an existing cluster cache configuration"""
    
    # Check if the cluster cache config file exists (filename = cluster name)
    path = f"config/clusterCache/{request.cluster}.json"
    if not os.path.exists(path):
        return ClusterCacheResponse(
            success=False,
            message=f"Cluster cache config file {request.cluster} does not exist"
        )
    
    # Verify that the referenced cluster exists
    cluster_path = f"config/clusters/{request.cluster}.json"
    if not os.path.exists(cluster_path):
        return ClusterCacheResponse(
            success=False,
            message=f"Referenced cluster '{request.cluster}' does not exist"
        )
    
    # Verify that the referenced registry exists
    registry_path = f"config/registry/{request.registry}.json"
    if not os.path.exists(registry_path):
        return ClusterCacheResponse(
            success=False,
            message=f"Referenced registry '{request.registry}' does not exist"
        )
    
    # Create the updated cluster cache config
    cluster_cache = ClusterCache(
        cluster_cache_details=ClusterCacheDetails(
            cluster=request.cluster,
            registry=request.registry,
            repo=request.repo
        )
    )
    
    # Save the updated cluster cache config to the file system
    with open(path, "w") as f:
        json.dump(cluster_cache.to_dict(), f, indent=4)
    
    return ClusterCacheResponse(
        success=True,
        message=f"Cluster cache config file {request.cluster} updated successfully"
    )
