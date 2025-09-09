import os
from pydantic import BaseModel
from classes.cluster_cache_models import ClusterCacheResponse

class DeleteClusterCacheRequest(BaseModel):
    cluster: str

async def delete_cluster_cache(request: DeleteClusterCacheRequest):
    """Delete a cluster cache configuration"""
    
    # Check if the cluster cache config file exists (filename = cluster name)
    path = f"config/clusterCache/{request.cluster}.json"
    if not os.path.exists(path):
        return ClusterCacheResponse(
            success=False,
            message=f"Cluster cache config file {request.cluster} does not exist"
        )
    
    try:
        # Delete the cluster cache config file
        os.remove(path)
        
        return ClusterCacheResponse(
            success=True,
            message=f"Cluster cache config file {request.cluster} deleted successfully"
        )
        
    except Exception as e:
        return ClusterCacheResponse(
            success=False,
            message=f"Error deleting cluster cache config file {request.cluster}: {str(e)}"
        )
