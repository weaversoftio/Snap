from pydantic import BaseModel
from flows.config.clusterCache.delete_cluster_cache import delete_cluster_cache, DeleteClusterCacheRequest
import os
import json

class DeleteClusterConfigRequest(BaseModel):
    name: str

class ClusterConfigResponse(BaseModel):
    success: bool
    message: str

async def delete_cluster_config(request: DeleteClusterConfigRequest):

    # TODO: Implement the logic to create the cluster config
    # check if the cluster config file exists under the config folder within the cluster config directory
    # if it does, return an error
    path = f"config/clusters/{request.name}.json"
    if not os.path.exists(path):
        return ClusterConfigResponse(
            success=False,
            message=f"Cluster config file {request.name} does not exist"
        )   
    
    # delete the cluster config file
    try:
         os.remove(path)
    except Exception as error:
        error_message = f"An unexpected error occurred: {error}, Failed to delete cluster config file {request.name}"
        print(error_message)
        return ClusterConfigResponse(
            success=False,
            message=error_message
        )
    
    # Also delete the cluster cache if it exists
    try:
        cluster_cache_request = DeleteClusterCacheRequest(cluster=request.name)
        cluster_cache_result = await delete_cluster_cache(cluster_cache_request)
        
        if cluster_cache_result.success:
            print(f"Cluster config file {request.name} and cluster cache deleted successfully")
            return ClusterConfigResponse(
                success=True,
                message=f"Cluster config file {request.name} and cluster cache deleted successfully"
            )
        else:
            # Cluster config was deleted but cluster cache deletion failed (might not exist)
            print(f"Cluster config file {request.name} deleted successfully, cluster cache deletion: {cluster_cache_result.message}")
            return ClusterConfigResponse(
                success=True,
                message=f"Cluster config file {request.name} deleted successfully (cluster cache: {cluster_cache_result.message})"
            )
    except Exception as e:
        # Cluster config was deleted but cluster cache deletion failed
        print(f"Cluster config file {request.name} deleted successfully, cluster cache deletion failed: {str(e)}")
        return ClusterConfigResponse(
            success=True,
            message=f"Cluster config file {request.name} deleted successfully (cluster cache deletion failed: {str(e)})"
        )

    
    