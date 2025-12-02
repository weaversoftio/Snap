from pydantic import BaseModel
from flows.config.clusterCache.delete_cluster_cache import delete_cluster_cache, DeleteClusterCacheRequest
from flows.config.watcher.watcher_config import list_watcher_configs, delete_watcher_config
from flows.config.hook.save_snaphook_config import delete_snaphook_config
from typing import Tuple, List
import os
import json
import logging

logger = logging.getLogger("automation_api")

class DeleteClusterConfigRequest(BaseModel):
    name: str

class ClusterConfigResponse(BaseModel):
    success: bool
    message: str


async def dispose_cluster_watchers(cluster_name: str) -> Tuple[int, List[str]]:
    """
    Dispose all watchers for a cluster by stopping them, removing from memory, and deleting config files.
    
    Args:
        cluster_name: Name of the cluster
        
    Returns:
        tuple: (count of disposed watchers, list of watcher names that were disposed)
    """
    disposed_count = 0
    disposed_watchers = []
    
    try:
        # Import watcher_instances from routes
        from routes.operator import watcher_instances
        
        # Get all watcher configs for this cluster
        all_configs = list_watcher_configs()
        cluster_watchers = [config for config in all_configs if config.cluster_name == cluster_name]
        
        logger.info(f"Disposing {len(cluster_watchers)} watchers for cluster '{cluster_name}'")
        
        # Stop and remove each watcher
        for watcher_config in cluster_watchers:
            watcher_name = watcher_config.name
            try:
                # Stop watcher if it's running in memory
                if watcher_name in watcher_instances:
                    watcher_instance = watcher_instances[watcher_name]
                    logger.info(f"Stopping watcher '{watcher_name}' for cluster '{cluster_name}'")
                    
                    # Stop the watcher (this stops the thread)
                    if watcher_instance.is_actually_running():
                        stop_success = watcher_instance.stop()
                        if not stop_success:
                            logger.warning(f"Failed to stop watcher '{watcher_name}', but continuing with removal")
                    
                    # Remove from memory
                    del watcher_instances[watcher_name]
                    logger.info(f"Removed watcher '{watcher_name}' from memory")
                
                # Delete watcher config file
                if delete_watcher_config(watcher_name):
                    logger.info(f"Deleted watcher config file for '{watcher_name}'")
                else:
                    logger.warning(f"Watcher config file for '{watcher_name}' may not have existed")
                
                disposed_count += 1
                disposed_watchers.append(watcher_name)
                
            except Exception as e:
                logger.error(f"Error disposing watcher '{watcher_name}': {e}")
                # Continue with other watchers even if one fails
        
        # Also check for any orphaned watcher instances (in memory but no config file)
        for watcher_name, watcher_instance in list(watcher_instances.items()):
            if watcher_instance.cluster_name == cluster_name:
                logger.warning(f"Found orphaned watcher instance '{watcher_name}' for cluster '{cluster_name}' - disposing")
                try:
                    if watcher_instance.is_actually_running():
                        watcher_instance.stop()
                    del watcher_instances[watcher_name]
                    disposed_count += 1
                    disposed_watchers.append(watcher_name)
                except Exception as e:
                    logger.error(f"Error disposing orphaned watcher '{watcher_name}': {e}")
        
        logger.info(f"Disposed {disposed_count} watchers for cluster '{cluster_name}': {disposed_watchers}")
        
    except Exception as e:
        logger.error(f"Error disposing watchers for cluster '{cluster_name}': {e}")
    
    return disposed_count, disposed_watchers


async def dispose_cluster_hooks(cluster_name: str) -> Tuple[int, List[str]]:
    """
    Dispose all hooks for a cluster by stopping them, removing from memory, and deleting config files.
    
    Args:
        cluster_name: Name of the cluster
        
    Returns:
        tuple: (count of disposed hooks, list of hook names that were disposed)
    """
    disposed_count = 0
    disposed_hooks = []
    
    try:
        # Import snaphook_instances from routes
        from routes.snaphook import snaphook_instances
        
        # Find all hooks for this cluster
        cluster_hooks = []
        for hook_name, hook_instance in list(snaphook_instances.items()):
            if hook_instance.cluster_name == cluster_name:
                cluster_hooks.append((hook_name, hook_instance))
        
        logger.info(f"Disposing {len(cluster_hooks)} hooks for cluster '{cluster_name}'")
        
        # Stop and remove each hook
        for hook_name, hook_instance in cluster_hooks:
            try:
                logger.info(f"Stopping hook '{hook_name}' for cluster '{cluster_name}'")
                
                # Stop the hook if it's running
                if hook_instance.is_running:
                    stop_success = hook_instance.stop()
                    if not stop_success:
                        logger.warning(f"Failed to stop hook '{hook_name}', but continuing with removal")
                
                # Remove from memory
                del snaphook_instances[hook_name]
                logger.info(f"Removed hook '{hook_name}' from memory")
                
                # Delete hook config file
                try:
                    result = await delete_snaphook_config(hook_name, cluster_name)
                    if result.success:
                        logger.info(f"Deleted hook config file for '{hook_name}'")
                    else:
                        logger.warning(f"Failed to delete hook config file for '{hook_name}': {result.message}")
                except Exception as e:
                    logger.warning(f"Error deleting hook config file for '{hook_name}': {e}")
                
                disposed_count += 1
                disposed_hooks.append(hook_name)
                
            except Exception as e:
                logger.error(f"Error disposing hook '{hook_name}': {e}")
                # Continue with other hooks even if one fails
        
        logger.info(f"Disposed {disposed_count} hooks for cluster '{cluster_name}': {disposed_hooks}")
        
    except Exception as e:
        logger.error(f"Error disposing hooks for cluster '{cluster_name}': {e}")
    
    return disposed_count, disposed_hooks


async def delete_cluster_config(request: DeleteClusterConfigRequest):
    """
    Delete a cluster configuration and dispose all associated watchers and hooks.
    
    This function:
    1. Disposes all watchers for the cluster (stops threads, removes from memory, deletes configs)
    2. Disposes all hooks for the cluster (stops hooks, removes from memory, deletes configs)
    3. Deletes the cluster cache
    4. Deletes the cluster config file
    
    Args:
        request: DeleteClusterConfigRequest with cluster name
        
    Returns:
        ClusterConfigResponse with success status and message
    """
    cluster_name = request.name
    
    # Check if the cluster config file exists
    path = f"config/clusters/{cluster_name}.json"
    if not os.path.exists(path):
        return ClusterConfigResponse(
            success=False,
            message=f"Cluster config file {cluster_name} does not exist"
        )
    
    # Step 1: Dispose all watchers for this cluster (stop threads, remove from memory, delete configs)
    logger.info(f"Disposing watchers for cluster '{cluster_name}' before deletion")
    watcher_count, disposed_watchers = await dispose_cluster_watchers(cluster_name)
    
    # Step 2: Dispose all hooks for this cluster (stop hooks, remove from memory, delete configs)
    logger.info(f"Disposing hooks for cluster '{cluster_name}' before deletion")
    hook_count, disposed_hooks = await dispose_cluster_hooks(cluster_name)
    
    # Step 3: Delete the cluster cache if it exists
    cluster_cache_message = ""
    try:
        cluster_cache_request = DeleteClusterCacheRequest(cluster=cluster_name)
        cluster_cache_result = await delete_cluster_cache(cluster_cache_request)
        if cluster_cache_result.success:
            cluster_cache_message = "cluster cache deleted"
        else:
            cluster_cache_message = f"cluster cache: {cluster_cache_result.message}"
    except Exception as e:
        cluster_cache_message = f"cluster cache deletion failed: {str(e)}"
        logger.warning(f"Cluster cache deletion failed for '{cluster_name}': {e}")
    
    # Step 4: Delete the cluster config file
    try:
        os.remove(path)
        logger.info(f"Deleted cluster config file for '{cluster_name}'")
    except Exception as error:
        error_message = f"An unexpected error occurred: {error}, Failed to delete cluster config file {cluster_name}"
        logger.error(error_message)
        return ClusterConfigResponse(
            success=False,
            message=error_message
        )
    
    # Build success message with details
    messages = []
    if watcher_count > 0:
        messages.append(f"{watcher_count} watcher(s) disposed: {', '.join(disposed_watchers)}")
    if hook_count > 0:
        messages.append(f"{hook_count} hook(s) disposed: {', '.join(disposed_hooks)}")
    if cluster_cache_message:
        messages.append(cluster_cache_message)
    
    detail_message = f"Cluster config file {cluster_name} deleted successfully"
    if messages:
        detail_message += f" ({'; '.join(messages)})"
    
    logger.info(f"Successfully deleted cluster '{cluster_name}': {detail_message}")
    
    return ClusterConfigResponse(
        success=True,
        message=detail_message
    )

    
    