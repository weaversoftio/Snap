import os
import json
from classes.cluster_cache_models import ClusterCacheListResponse

async def list_cluster_cache():
    """List all cluster cache configurations"""
    
    cluster_cache_dir = "config/clusterCache"
    
    # Check if the cluster cache directory exists
    if not os.path.exists(cluster_cache_dir):
        return ClusterCacheListResponse(
            success=False,
            cluster_caches=[],
            message="Cluster cache directory does not exist"
        )
    
    cluster_caches = []
    
    try:
        # Get all JSON files in the cluster cache directory
        for filename in os.listdir(cluster_cache_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(cluster_cache_dir, filename)
                with open(file_path, 'r') as f:
                    cluster_cache_data = json.load(f)
                    cluster_caches.append(cluster_cache_data)
        
        return ClusterCacheListResponse(
            success=True,
            cluster_caches=cluster_caches,
            message=f"Found {len(cluster_caches)} cluster cache configurations"
        )
        
    except Exception as e:
        return ClusterCacheListResponse(
            success=False,
            cluster_caches=[],
            message=f"Error reading cluster cache configurations: {str(e)}"
        )
