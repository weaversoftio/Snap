"""
Operator management routes for SnapWatcher.
Provides endpoints to start, stop, and manage the Kubernetes operator.
"""

import os
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from classes.operator_watcher import SnapWatcherOperator
from classes.clusterconfig import ClusterConfig
from classes.websocket_log_handler import log_info, log_error, log_warning, log_success
from flows.config.watcher.watcher_config import (
    WatcherConfig, save_watcher_config, load_watcher_config, 
    list_watcher_configs, delete_watcher_config, update_watcher_status,
    load_watcher_configs_on_startup, async_load_watcher_config,
    async_update_watcher_status
)

logger = logging.getLogger("automation_api")
router = APIRouter()

# Global watcher instances dictionary - similar to snaphook_instances
watcher_instances: Dict[str, SnapWatcherOperator] = {}


def _create_watcher_instance(config: WatcherConfig) -> SnapWatcherOperator:
    """
    Helper function to create a SnapWatcherOperator instance from a WatcherConfig.
    
    Args:
        config: WatcherConfig object
        
    Returns:
        SnapWatcherOperator: Created operator instance
    """
    return SnapWatcherOperator(
        cluster_name=config.cluster_name,
        cluster_config=ClusterConfig(**config.cluster_config),
        scope=config.scope,
        namespace=config.namespace,
        auto_delete_pod=config.auto_delete_pod,
        trigger=config.trigger
    )




class SnapWatcherCreateRequest(BaseModel):
    """Request model for creating a SnapWatcher."""
    name: str
    cluster_name: str
    cluster_config: ClusterConfig
    scope: str = "cluster"
    trigger: str = "startupProbe"
    namespace: Optional[str] = None
    auto_delete_pod: bool = True


class SnapWatcherUpdateRequest(BaseModel):
    """Request model for updating a SnapWatcher."""
    scope: Optional[str] = None
    trigger: Optional[str] = None
    namespace: Optional[str] = None
    auto_delete_pod: Optional[bool] = None


class SnapWatcherResponse(BaseModel):
    """Response model for SnapWatcher."""
    name: str
    cluster_name: str
    cluster_config: Optional[Dict[str, Any]] = None
    scope: str
    trigger: str
    namespace: Optional[str] = None
    status: str
    auto_delete_pod: bool
    created_at: str
    updated_at: str


class SnapWatcherListResponse(BaseModel):
    """Response model for SnapWatcher list."""
    success: bool
    watchers: List[SnapWatcherResponse]
    message: Optional[str] = None








@router.get("/watchers/status")
async def get_all_watchers_status():
    """
    Get the status of all active SnapWatchers.
    
    Returns:
        Dict containing status of all watchers
    """
    try:
        watcher_statuses = {}
        
        for watcher_name, watcher_instance in watcher_instances.items():
            watcher_statuses[watcher_name] = {
                "running": watcher_instance.is_actually_running(),
                "cluster_name": watcher_instance.cluster_name,
                "scope": watcher_instance.scope,
                "namespace": watcher_instance.namespace,
                "auto_delete_pod": watcher_instance.auto_delete_pod,
                "is_ready": watcher_instance.is_ready(),
                "status": watcher_instance.get_status()
            }
        
        return {
            "success": True,
            "active_watchers": len(watcher_instances),
            "watchers": watcher_statuses
        }
        
    except Exception as e:
        log_error(logger, 'SnapApi', 'Error Handling', f'Failed to get watchers status: {e}')
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get watchers status: {str(e)}"
        )


# SnapWatcher Configuration Management Endpoints

@router.post("/snapwatcher", response_model=SnapWatcherResponse)
async def create_snapwatcher(request: SnapWatcherCreateRequest):
    """
    Create a new SnapWatcher configuration.
    
    Args:
        request: SnapWatcher creation request
        
    Returns:
        SnapWatcherResponse: Created SnapWatcher configuration
    """
    try:
        # Check if watcher with same name already exists
        existing_config = load_watcher_config(request.name)
        if existing_config:
            raise HTTPException(
                status_code=400,
                detail=f"SnapWatcher with name '{request.name}' already exists"
            )
        
        # Create new watcher config
        watcher_config = WatcherConfig(
            name=request.name,
            cluster_name=request.cluster_name,
            cluster_config=request.cluster_config.model_dump(),
            scope=request.scope,
            trigger=request.trigger,
            namespace=request.namespace,
            status="stopped",
            auto_delete_pod=request.auto_delete_pod
        )
        
        # Save configuration
        if not save_watcher_config(watcher_config):
            raise HTTPException(
                status_code=500,
                detail="Failed to save SnapWatcher configuration"
            )
        
        # Automatically start the watcher after creation
        try:
            # Create watcher instance
            watcher_instance = _create_watcher_instance(watcher_config)
            
            if not watcher_instance.is_ready():
                log_warning(logger, 'SnapApi', 'SnapWatcher Management', f'Watcher {request.name} is not ready, will not auto-start')
            else:
                # Start the watcher
                success = watcher_instance.start()
                if success:
                    # Store instance
                    watcher_instances[request.name] = watcher_instance
                    
                    # Update watcher status to running
                    update_watcher_status(request.name, "running")
                    
                    # Reload config to get updated status
                    watcher_config = load_watcher_config(request.name)
                    
                    log_success(logger, 'SnapApi', 'SnapWatcher Management', f'SnapWatcher created and started: {request.name}')
                else:
                    log_error(logger, 'SnapApi', 'SnapWatcher Management', f'Failed to start SnapWatcher {request.name}')
                    # Don't fail the creation if start fails, just log the error
                    log_info(logger, 'SnapApi', 'SnapWatcher Management', f'SnapWatcher created but not started: {request.name}')
        except Exception as start_error:
            log_error(logger, 'SnapApi', 'Error Handling', f'Failed to start SnapWatcher {request.name}: {start_error}')
            # Don't fail the creation if start fails, just log the error
            log_info(logger, 'SnapApi', 'SnapWatcher Management', f'SnapWatcher created but not started: {request.name}')
        
        return SnapWatcherResponse(**watcher_config.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, 'SnapApi', 'Error Handling', f'Failed to create SnapWatcher: {e}')
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create SnapWatcher: {str(e)}"
        )


@router.get("/snapwatchers/{cluster_name}", response_model=SnapWatcherListResponse)
async def get_snapwatchers(cluster_name: str):
    """
    Get all SnapWatchers for a specific cluster.
    
    Args:
        cluster_name: Name of the cluster
        
    Returns:
        SnapWatcherListResponse: List of SnapWatchers for the cluster
    """
    try:
        all_configs = list_watcher_configs()
        cluster_configs = [config for config in all_configs if config.cluster_name == cluster_name]
        
        # Clean up orphaned watcher instances (running but no JSON file)
        config_names = {config.name for config in cluster_configs}
        orphaned_watchers = []
        for watcher_name, watcher_instance in list(watcher_instances.items()):
            if watcher_name not in config_names:
                logger.warning(f"Found orphaned watcher instance '{watcher_name}' - stopping and removing")
                try:
                    watcher_instance.stop()
                except Exception as e:
                    logger.error(f"Error stopping orphaned watcher '{watcher_name}': {e}")
                finally:
                    del watcher_instances[watcher_name]
                    orphaned_watchers.append(watcher_name)
        
        if orphaned_watchers:
            logger.info(f"Cleaned up {len(orphaned_watchers)} orphaned watcher instances: {orphaned_watchers}")
        
        watchers = []
        for config in cluster_configs:
            # Check if this watcher is actually running in watcher_instances
            actual_status = "stopped"
            if config.name in watcher_instances:
                watcher_instance = watcher_instances[config.name]
                # Use is_actually_running() which checks both flag and thread status
                if watcher_instance.is_actually_running():
                    actual_status = "running"
                else:
                    actual_status = "stopped"
            else:
                actual_status = "stopped"
            
            # Update stored status if it doesn't match actual status
            if config.status != actual_status:
                update_watcher_status(config.name, actual_status)
                config.status = actual_status
            
            config_dict = config.to_dict()
            config_dict['cluster_config'] = config.cluster_config
            watchers.append(SnapWatcherResponse(**config_dict))
        
        return SnapWatcherListResponse(
            success=True,
            watchers=watchers,
            message=f"Found {len(watchers)} SnapWatchers for cluster '{cluster_name}'"
        )
        
    except Exception as e:
        log_error(logger, 'SnapApi', 'Error Handling', f'Failed to get SnapWatchers for cluster {cluster_name}: {e}')
        return SnapWatcherListResponse(
            success=False,
            watchers=[],
            message=f"Failed to get SnapWatchers: {str(e)}"
        )


@router.get("/snapwatcher/{watcher_name}", response_model=SnapWatcherResponse)
async def get_snapwatcher(watcher_name: str):
    """
    Get a specific SnapWatcher configuration.
    
    Args:
        watcher_name: Name of the SnapWatcher
        
    Returns:
        SnapWatcherResponse: SnapWatcher configuration
    """
    try:
        config = load_watcher_config(watcher_name)
        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"SnapWatcher '{watcher_name}' not found"
            )
        
        config_dict = config.to_dict()
        config_dict['cluster_config'] = config.cluster_config
        return SnapWatcherResponse(**config_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, 'SnapApi', 'Error Handling', f'Failed to get SnapWatcher {watcher_name}: {e}')
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get SnapWatcher: {str(e)}"
        )


@router.put("/snapwatcher/{watcher_name}", response_model=SnapWatcherResponse)
async def update_snapwatcher(watcher_name: str, request: SnapWatcherUpdateRequest):
    """
    Update a SnapWatcher configuration.
    
    Args:
        watcher_name: Name of the SnapWatcher to update
        request: Update request with new values
        
    Returns:
        SnapWatcherResponse: Updated SnapWatcher configuration
    """
    try:
        config = load_watcher_config(watcher_name)
        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"SnapWatcher '{watcher_name}' not found"
            )
        
        # Update fields if provided
        if request.scope is not None:
            config.scope = request.scope
        if request.trigger is not None:
            config.trigger = request.trigger
        if request.namespace is not None:
            config.namespace = request.namespace
        
        # Save updated configuration
        if not save_watcher_config(config):
            raise HTTPException(
                status_code=500,
                detail="Failed to save updated SnapWatcher configuration"
            )
        
        log_success(logger, 'SnapApi', 'SnapWatcher Management', f'SnapWatcher updated: {watcher_name}')
        
        config_dict = config.to_dict()
        config_dict['cluster_config'] = config.cluster_config
        return SnapWatcherResponse(**config_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, 'SnapApi', 'Error Handling', f'Failed to update SnapWatcher {watcher_name}: {e}')
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update SnapWatcher: {str(e)}"
        )


@router.delete("/snapwatcher/{watcher_name}")
async def delete_snapwatcher(watcher_name: str):
    """
    Delete a SnapWatcher configuration.
    
    Args:
        watcher_name: Name of the SnapWatcher to delete
        
    Returns:
        dict: Success message
    """
    try:
        config = load_watcher_config(watcher_name)
        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"SnapWatcher '{watcher_name}' not found"
            )
        
        # Stop watcher if running
        if config.status == "running":
            await stop_snapwatcher(watcher_name)
        
        # Remove from watcher_instances if it exists
        if watcher_name in watcher_instances:
            del watcher_instances[watcher_name]
        
        # Delete configuration
        if not delete_watcher_config(watcher_name):
            raise HTTPException(
                status_code=500,
                detail="Failed to delete SnapWatcher configuration"
            )
        
        log_success(logger, 'SnapApi', 'SnapWatcher Management', f'SnapWatcher deleted: {watcher_name}')
        
        return {"success": True, "message": f"SnapWatcher '{watcher_name}' deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, 'SnapApi', 'Error Handling', f'Failed to delete SnapWatcher {watcher_name}: {e}')
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete SnapWatcher: {str(e)}"
        )


@router.post("/snapwatcher/{watcher_name}/start", response_model=SnapWatcherResponse)
async def start_snapwatcher(watcher_name: str):
    """
    Start a SnapWatcher.
    
    Args:
        watcher_name: Name of the SnapWatcher to start
        
    Returns:
        SnapWatcherResponse: Updated SnapWatcher configuration
    """
    try:
        config = load_watcher_config(watcher_name)
        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"SnapWatcher '{watcher_name}' not found"
            )
        
        # Check if actually running (not just the flag)
        if watcher_name in watcher_instances:
            watcher_instance = watcher_instances[watcher_name]
            if watcher_instance.is_actually_running():
                raise HTTPException(
                    status_code=400,
                    detail=f"SnapWatcher '{watcher_name}' is already running"
                )
        elif config.status == "running":
            # Status says running but no instance - update status
            update_watcher_status(watcher_name, "stopped")
            config.status = "stopped"
        
        # Create watcher instance if it doesn't exist
        if watcher_name not in watcher_instances:
            watcher_instance = _create_watcher_instance(config)
            watcher_instances[watcher_name] = watcher_instance
        else:
            watcher_instance = watcher_instances[watcher_name]
        
        # Start the watcher
        success = watcher_instance.start()
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start SnapWatcher '{watcher_name}'"
            )
        
        # Update watcher status
        update_watcher_status(watcher_name, "running")
        
        # Reload config to get updated status
        updated_config = load_watcher_config(watcher_name)
        
        log_success(logger, 'SnapApi', 'SnapWatcher Management', f'SnapWatcher started: {watcher_name}')
        
        return SnapWatcherResponse(**updated_config.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, 'SnapApi', 'Error Handling', f'Failed to start SnapWatcher {watcher_name}: {e}')
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start SnapWatcher: {str(e)}"
        )


@router.post("/snapwatcher/{watcher_name}/stop", response_model=SnapWatcherResponse)
async def stop_snapwatcher(watcher_name: str):
    """
    Stop a SnapWatcher.
    
    Args:
        watcher_name: Name of the SnapWatcher to stop
        
    Returns:
        SnapWatcherResponse: Updated SnapWatcher configuration
    """
    try:
        config = load_watcher_config(watcher_name)
        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"SnapWatcher '{watcher_name}' not found"
            )
        
        # Check if actually running (not just the flag)
        if watcher_name in watcher_instances:
            watcher_instance = watcher_instances[watcher_name]
            if not watcher_instance.is_actually_running():
                # Not actually running, update status and return
                update_watcher_status(watcher_name, "stopped")
                updated_config = load_watcher_config(watcher_name)
                config_dict = updated_config.to_dict()
                config_dict['cluster_config'] = updated_config.cluster_config
                return SnapWatcherResponse(**config_dict)
            
            # Actually running, stop it
            success = watcher_instance.stop()
            if not success:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to stop SnapWatcher '{watcher_name}'"
                )
            # Remove from instances
            del watcher_instances[watcher_name]
        else:
            # No instance but status says running - update status
            if config.status == "running":
                log_warning(logger, 'SnapApi', 'SnapWatcher Management', f'Watcher instance not found for {watcher_name}, updating status to stopped')
                update_watcher_status(watcher_name, "stopped")
                updated_config = load_watcher_config(watcher_name)
                config_dict = updated_config.to_dict()
                config_dict['cluster_config'] = updated_config.cluster_config
                return SnapWatcherResponse(**config_dict)
        
        # Update watcher status
        update_watcher_status(watcher_name, "stopped")
        
        # Reload config to get updated status
        updated_config = load_watcher_config(watcher_name)
        
        log_success(logger, 'SnapApi', 'SnapWatcher Management', f'SnapWatcher stopped: {watcher_name}')
        
        return SnapWatcherResponse(**updated_config.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, 'SnapApi', 'Error Handling', f'Failed to stop SnapWatcher {watcher_name}: {e}')
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop SnapWatcher: {str(e)}"
        )


@router.get("/snapwatcher/{watcher_name}/status", response_model=SnapWatcherResponse)
async def get_snapwatcher_status(watcher_name: str):
    """
    Get the status of a specific SnapWatcher.
    
    Args:
        watcher_name: Name of the SnapWatcher
        
    Returns:
        SnapWatcherResponse: SnapWatcher configuration with current status
    """
    try:
        # Use async version to avoid blocking the event loop
        config = await async_load_watcher_config(watcher_name)
        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"SnapWatcher '{watcher_name}' not found"
            )
        
        # Check if this watcher is actually running in watcher_instances
        actual_status = "stopped"
        if watcher_name in watcher_instances:
            watcher_instance = watcher_instances[watcher_name]
            # Use is_actually_running() which checks both flag and thread status
            if watcher_instance.is_actually_running():
                actual_status = "running"
            else:
                actual_status = "stopped"
        else:
            actual_status = "stopped"
        
        # Update stored status if it doesn't match actual status
        if config.status != actual_status:
            # Use async version to avoid blocking the event loop
            await async_update_watcher_status(watcher_name, actual_status)
            config.status = actual_status
        
        config_dict = config.to_dict()
        config_dict['cluster_config'] = config.cluster_config
        return SnapWatcherResponse(**config_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, 'SnapApi', 'Error Handling', f'Failed to get SnapWatcher status {watcher_name}: {e}')
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get SnapWatcher status: {str(e)}"
        )


# Startup function to load watcher configs and auto-start them
async def load_watcher_configs_on_startup():
    """Load all watcher configurations on startup and auto-start them."""
    try:
        from flows.config.watcher.watcher_config import load_watcher_configs_on_startup as load_configs
        configs = load_configs()
        log_info(logger, 'SnapApi', 'Configuration Loading', f'SnapAPI: Loaded {len(configs)} watcher configurations on startup')
        
        # Auto-start SnapWatchers that were running before restart
        if configs:
            log_info(logger, 'SnapApi', 'Configuration Loading', f'Auto-starting SnapWatchers that were running before restart...')
            started_count = 0
            failed_count = 0
            
            for config in configs:
                try:
                    if config.status == "running":
                        log_info(logger, 'SnapApi', 'SnapWatcher Management', f'Restoring SnapWatcher: {config.name} (was running before restart)')
                        
                        # Create watcher instance
                        watcher_instance = _create_watcher_instance(config)
                        
                        if watcher_instance.is_ready():
                            # Start the watcher
                            success = watcher_instance.start()
                            if success:
                                # Store instance
                                watcher_instances[config.name] = watcher_instance
                                started_count += 1
                                log_success(logger, 'SnapApi', 'SnapWatcher Management', f'Successfully restored SnapWatcher: {config.name}')
                            else:
                                failed_count += 1
                                log_error(logger, 'SnapApi', 'SnapWatcher Management', f'Failed to restore SnapWatcher: {config.name}')
                        else:
                            failed_count += 1
                            log_error(logger, 'SnapApi', 'SnapWatcher Management', f'SnapWatcher {config.name} is not ready, cannot restore')
                    else:
                        log_info(logger, 'SnapApi', 'SnapWatcher Management', f'SnapWatcher {config.name} was stopped, not auto-starting')
                        
                except Exception as e:
                    log_error(logger, 'SnapApi', 'Error Handling', f'Error processing SnapWatcher {config.name}: {e}')
                    failed_count += 1
            
            log_success(logger, 'SnapApi', 'Configuration Loading', f'SnapWatcher restoration completed: {started_count} restored, {failed_count} failed')
        else:
            log_info(logger, 'SnapApi', 'Configuration Loading', f'No SnapWatcher configurations found to restore')
            
        return configs
    except Exception as e:
        log_error(logger, 'SnapApi', 'Error Handling', f'Failed to load watcher configurations on startup: {e}')
        return []
