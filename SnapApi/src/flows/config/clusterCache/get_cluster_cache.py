import os
import json
from classes.cluster_cache_models import ClusterCacheResponse, ClusterCacheDetails

async def get_cluster_cache(cluster_name: str):
    """Get cluster cache configuration for a specific cluster"""
    
    # Check if the cluster cache config file exists (filename = cluster name)
    path = f"config/clusterCache/{cluster_name}.json"
    if not os.path.exists(path):
        return ClusterCacheResponse(
            success=False,
            message=f"Cluster cache config file {cluster_name} does not exist"
        )
    
    try:
        with open(path, 'r') as f:
            cluster_cache_data = json.load(f)
        
        return ClusterCacheResponse(
            success=True,
            message=f"Cluster cache config for {cluster_name} retrieved successfully",
            cluster_cache_details=ClusterCacheDetails(
                cluster=cluster_cache_data["cluster_cache_details"]["cluster"],
                registry=cluster_cache_data["cluster_cache_details"]["registry"],
                repo=cluster_cache_data["cluster_cache_details"]["repo"]
            )
        )
        
    except Exception as e:
        return ClusterCacheResponse(
            success=False,
            message=f"Error reading cluster cache config for {cluster_name}: {str(e)}"
        )
