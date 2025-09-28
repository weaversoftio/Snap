"""
Operator management routes for SnapWatcher.
Provides endpoints to start, stop, and manage the Kubernetes operator.
"""

import os
import threading
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from classes.operator_watcher import SnapWatcherOperator, set_global_operator
from classes.clusterconfig import ClusterConfig
from flows.config.watcher.watcher_config import (
    WatcherConfig, save_watcher_config, load_watcher_config, 
    list_watcher_configs, delete_watcher_config, update_watcher_status,
    load_watcher_configs_on_startup
)

logger = logging.getLogger("automation_api")
router = APIRouter()

# Global operator instance and thread
operator_instance: Optional[SnapWatcherOperator] = None
operator_thread: Optional[threading.Thread] = None
operator_running = False

# Dictionary to manage multiple watcher instances
active_watchers: Dict[str, Dict[str, Any]] = {}


class OperatorStartRequest(BaseModel):
    """Request model for starting the operator."""
    cluster_name: str
    cluster_config: ClusterConfig
    scope: str = "cluster"
    namespace: Optional[str] = None
    auto_delete_pod: bool = True


class OperatorStatusResponse(BaseModel):
    """Response model for operator status."""
    running: bool
    cluster_name: Optional[str] = None
    error: Optional[str] = None


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


def run_operator(namespace=None):
    """Run the operator in a separate thread."""
    global operator_running
    try:
        logger.info("Starting SnapWatcher operator...")
        import kopf
        
        if namespace:
            logger.info(f"Starting operator with namespace scope: {namespace}")
            kopf.run(namespace=namespace)
        else:
            logger.info("Starting operator with cluster-wide scope")
            kopf.run(clusterwide=True)
    except Exception as e:
        logger.error(f"Operator thread error: {e}")
        operator_running = False


@router.post("/start", response_model=OperatorStatusResponse)
async def start_operator(request: OperatorStartRequest, background_tasks: BackgroundTasks):
    """
    Start the SnapWatcher operator with the provided cluster configuration.
    
    Args:
        request: Operator start request containing cluster name and config
        background_tasks: FastAPI background tasks
        
    Returns:
        OperatorStatusResponse: Status of the operator
    """
    global operator_instance, operator_thread, operator_running
    
    if operator_running:
        raise HTTPException(
            status_code=400, 
            detail="Operator is already running. Stop it first before starting a new one."
        )
    
    try:
        # Create operator instance with cluster config
        operator_instance = SnapWatcherOperator(
            cluster_name=request.cluster_name,
            cluster_config=request.cluster_config,
            scope=request.scope,
            namespace=request.namespace,
            auto_delete_pod=request.auto_delete_pod
        )
        
        # Set the global operator instance for kopf event handlers
        set_global_operator(operator_instance)
        
        if not operator_instance.is_ready():
            raise HTTPException(
                status_code=400,
                detail="Operator is not ready. Check cluster configuration."
            )
        
        # Start operator in background thread
        namespace_param = request.namespace if request.scope == "namespace" else None
        operator_thread = threading.Thread(target=run_operator, args=(namespace_param,), daemon=True)
        operator_thread.start()
        operator_running = True
        
        logger.info(f"SnapWatcher operator started successfully for cluster: {request.cluster_name}")
        
        return OperatorStatusResponse(
            running=True,
            cluster_name=request.cluster_name
        )
        
    except Exception as e:
        logger.error(f"Failed to start operator: {e}")
        operator_running = False
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start operator: {str(e)}"
        )


@router.post("/stop", response_model=OperatorStatusResponse)
async def stop_operator():
    """
    Stop the SnapWatcher operator.
    
    Returns:
        OperatorStatusResponse: Status of the operator
    """
    global operator_instance, operator_thread, operator_running
    
    if not operator_running:
        return OperatorStatusResponse(
            running=False,
            error="Operator is not running"
        )
    
    try:
        # Note: kopf.run() doesn't have a direct stop method
        # The thread will be daemon=True so it will stop when the main process stops
        # For now, we'll just mark it as stopped
        operator_running = False
        operator_instance = None
        operator_thread = None
        
        # Clear the global operator instance
        set_global_operator(None)
        
        logger.info("SnapWatcher operator stopped")
        
        return OperatorStatusResponse(
            running=False,
            cluster_name=None
        )
        
    except Exception as e:
        logger.error(f"Failed to stop operator: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop operator: {str(e)}"
        )


@router.get("/status", response_model=OperatorStatusResponse)
async def get_operator_status():
    """
    Get the current status of the SnapWatcher operator.
    
    Returns:
        OperatorStatusResponse: Current status of the operator
    """
    global operator_instance, operator_running
    
    if not operator_running or operator_instance is None:
        return OperatorStatusResponse(
            running=False,
            cluster_name=None
        )
    
    return OperatorStatusResponse(
        running=True,
        cluster_name=operator_instance.cluster_name
    )


@router.get("/watchers/status")
async def get_all_watchers_status():
    """
    Get the status of all active SnapWatchers.
    
    Returns:
        Dict containing status of all watchers
    """
    try:
        watcher_statuses = {}
        
        for watcher_name, watcher_info in active_watchers.items():
            watcher_statuses[watcher_name] = {
                "running": watcher_info["running"],
                "cluster_name": watcher_info["config"].cluster_name,
                "scope": watcher_info["config"].scope,
                "namespace": watcher_info["config"].namespace,
                "thread_alive": watcher_info["thread"].is_alive() if watcher_info["thread"] else False
            }
        
        return {
            "success": True,
            "active_watchers": len(active_watchers),
            "watchers": watcher_statuses
        }
        
    except Exception as e:
        logger.error(f"Failed to get watchers status: {e}")
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
            # Check if there's already a running operator
            if operator_running:
                logger.warning(f"Operator is already running. Stopping current operator to start new watcher: {request.name}")
                await stop_operator()
            
            # Start the operator with this watcher's configuration
            start_request = OperatorStartRequest(
                cluster_name=request.cluster_name,
                cluster_config=request.cluster_config,
                scope=request.scope,
                namespace=request.namespace,
                auto_delete_pod=request.auto_delete_pod
            )
            
            # Start the operator
            await start_operator(start_request, BackgroundTasks())
            
            # Add watcher to active_watchers dictionary for status tracking
            active_watchers[request.name] = {
                "instance": operator_instance,
                "thread": operator_thread,
                "config": watcher_config,
                "running": True
            }
            
            # Update watcher status to running
            update_watcher_status(request.name, "running")
            
            # Reload config to get updated status
            watcher_config = load_watcher_config(request.name)
            
            logger.info(f"SnapWatcher created and started: {request.name}")
            
        except Exception as start_error:
            logger.error(f"Failed to start SnapWatcher {request.name}: {start_error}")
            # Don't fail the creation if start fails, just log the error
            logger.info(f"SnapWatcher created but not started: {request.name}")
        
        return SnapWatcherResponse(**watcher_config.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create SnapWatcher: {e}")
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
        
        watchers = []
        for config in cluster_configs:
            # Check if this watcher is actually running in active_watchers
            actual_status = "stopped"
            if config.name in active_watchers:
                watcher_info = active_watchers[config.name]
                if watcher_info["running"] and watcher_info["thread"].is_alive():
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
        logger.error(f"Failed to get SnapWatchers for cluster {cluster_name}: {e}")
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
        logger.error(f"Failed to get SnapWatcher {watcher_name}: {e}")
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
        
        logger.info(f"SnapWatcher updated: {watcher_name}")
        
        config_dict = config.to_dict()
        config_dict['cluster_config'] = config.cluster_config
        return SnapWatcherResponse(**config_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update SnapWatcher {watcher_name}: {e}")
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
        
        # Delete configuration
        if not delete_watcher_config(watcher_name):
            raise HTTPException(
                status_code=500,
                detail="Failed to delete SnapWatcher configuration"
            )
        
        logger.info(f"SnapWatcher deleted: {watcher_name}")
        
        return {"success": True, "message": f"SnapWatcher '{watcher_name}' deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete SnapWatcher {watcher_name}: {e}")
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
        
        if config.status == "running":
            raise HTTPException(
                status_code=400,
                detail=f"SnapWatcher '{watcher_name}' is already running"
            )
        
        # Start the operator with this watcher's configuration
        start_request = OperatorStartRequest(
            cluster_name=config.cluster_name,
            cluster_config=ClusterConfig(**config.cluster_config),
            scope=config.scope,
            namespace=config.namespace
        )
        
        # Use the existing start_operator logic
        await start_operator(start_request, BackgroundTasks())
        
        # Add watcher to active_watchers dictionary for status tracking
        active_watchers[watcher_name] = {
            "instance": operator_instance,
            "thread": operator_thread,
            "config": config,
            "running": True
        }
        
        # Update watcher status
        update_watcher_status(watcher_name, "running")
        
        # Reload config to get updated status
        updated_config = load_watcher_config(watcher_name)
        
        logger.info(f"SnapWatcher started: {watcher_name}")
        
        return SnapWatcherResponse(**updated_config.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start SnapWatcher {watcher_name}: {e}")
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
        
        if config.status != "running":
            raise HTTPException(
                status_code=400,
                detail=f"SnapWatcher '{watcher_name}' is not running"
            )
        
        # Stop the operator
        await stop_operator()
        
        # Remove watcher from active_watchers dictionary
        if watcher_name in active_watchers:
            del active_watchers[watcher_name]
        
        # Update watcher status
        update_watcher_status(watcher_name, "stopped")
        
        # Reload config to get updated status
        updated_config = load_watcher_config(watcher_name)
        
        logger.info(f"SnapWatcher stopped: {watcher_name}")
        
        return SnapWatcherResponse(**updated_config.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop SnapWatcher {watcher_name}: {e}")
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
        config = load_watcher_config(watcher_name)
        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"SnapWatcher '{watcher_name}' not found"
            )
        
        # Check if this watcher is actually running in active_watchers
        actual_status = "stopped"
        if watcher_name in active_watchers:
            watcher_info = active_watchers[watcher_name]
            if watcher_info["running"] and watcher_info["thread"].is_alive():
                actual_status = "running"
            else:
                actual_status = "stopped"
        else:
            actual_status = "stopped"
        
        # Update stored status if it doesn't match actual status
        if config.status != actual_status:
            update_watcher_status(watcher_name, actual_status)
            config.status = actual_status
        
        config_dict = config.to_dict()
        config_dict['cluster_config'] = config.cluster_config
        return SnapWatcherResponse(**config_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get SnapWatcher status {watcher_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get SnapWatcher status: {str(e)}"
        )


def start_individual_watcher(config: WatcherConfig) -> bool:
    """
    Start an individual SnapWatcher.
    
    Args:
        config: WatcherConfig instance to start
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Starting individual SnapWatcher: {config.name}")
        
        # Create operator instance for this watcher
        watcher_instance = SnapWatcherOperator(
            cluster_name=config.cluster_name,
            cluster_config=ClusterConfig(**config.cluster_config),
            scope=config.scope,
            namespace=config.namespace,
            auto_delete_pod=config.auto_delete_pod
        )
        
        if not watcher_instance.is_ready():
            logger.error(f"SnapWatcher {config.name} is not ready. Check cluster configuration.")
            return False
        
        # Start operator in background thread
        namespace_param = config.namespace if config.scope == "namespace" else None
        watcher_thread = threading.Thread(
            target=run_operator, 
            args=(namespace_param,), 
            daemon=True,
            name=f"SnapWatcher-{config.name}"
        )
        watcher_thread.start()
        
        # Store watcher info in active_watchers
        active_watchers[config.name] = {
            "instance": watcher_instance,
            "thread": watcher_thread,
            "config": config,
            "running": True
        }
        
        # Update watcher status
        update_watcher_status(config.name, "running")
        
        logger.info(f"Successfully started SnapWatcher: {config.name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to start SnapWatcher {config.name}: {e}")
        update_watcher_status(config.name, "error")
        return False


# Startup function to load watcher configs and auto-start them
async def load_watcher_configs_on_startup():
    """Load all watcher configurations on startup and auto-start them."""
    try:
        from flows.config.watcher.watcher_config import load_watcher_configs_on_startup as load_configs
        configs = load_configs()
        logger.info(f"SnapAPI: Loaded {len(configs)} watcher configurations on startup")
        
        # Clear all "running" statuses since API just restarted
        logger.info("Clearing all 'running' statuses since API restarted...")
        for config in configs:
            if config.status == "running":
                update_watcher_status(config.name, "stopped")
                logger.info(f"Marked SnapWatcher '{config.name}' as stopped (API restart)")
        
        # Check if we should auto-start watchers based on WATCHER_MODE
        watcher_mode = os.getenv("WATCHER_MODE", "kubernetes")
        if watcher_mode.lower() == "compose":
            logger.info("WATCHER_MODE=compose detected, skipping SnapWatcher auto-start")
            return
        
        # Auto-start all existing Snapwatchers
        if configs:
            logger.info("Auto-starting all existing Snapwatchers...")
            started_count = 0
            failed_count = 0
            
            for config in configs:
                try:
                    if config.status != "running":
                        logger.info(f"Starting SnapWatcher: {config.name}")
                        
                        # Start the individual watcher
                        if start_individual_watcher(config):
                            started_count += 1
                        else:
                            failed_count += 1
                    else:
                        logger.info(f"SnapWatcher {config.name} is already running")
                        started_count += 1
                        
                except Exception as e:
                    logger.error(f"Error processing SnapWatcher {config.name}: {e}")
                    failed_count += 1
            
            logger.info(f"SnapWatcher auto-start completed: {started_count} started, {failed_count} failed")
        else:
            logger.info("No SnapWatcher configurations found to auto-start")
            
        return configs
    except Exception as e:
        logger.error(f"Failed to load watcher configurations on startup: {e}")
        return []
