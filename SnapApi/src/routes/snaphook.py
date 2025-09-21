"""
SnapHook management routes.
Provides endpoints to create, start, stop, and manage SnapHook webhooks.
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from classes.snaphook import SnapHook
from classes.clusterconfig import ClusterConfig, ClusterConfigDetails
from flows.config.hook.save_snaphook_config import save_snaphook_config, update_snaphook_config_start_time, delete_snaphook_config, list_snaphook_configs

logger = logging.getLogger("automation_api")
router = APIRouter()

# Global SnapHook instances
snaphook_instances: Dict[str, SnapHook] = {}


class SnapHookCreateRequest(BaseModel):
    """Request model for creating a SnapHook."""
    name: str
    cluster_name: str
    cluster_config: dict
    webhook_url: Optional[str] = None
    namespace: str = "snap"
    cert_expiry_days: int = 365


class SnapHookResponse(BaseModel):
    """Response model for SnapHook."""
    name: str
    cluster_name: str
    webhook_url: str
    namespace: str
    is_running: bool
    cert_expiry_days: int
    status: Dict[str, Any]


class SnapHookListResponse(BaseModel):
    """Response model for SnapHook list."""
    success: bool
    snaphooks: List[SnapHookResponse]
    message: Optional[str] = None


@router.post("/snaphook", response_model=SnapHookResponse)
async def create_snaphook(request: SnapHookCreateRequest):
    """
    Create a new SnapHook instance.
    
    Args:
        request: SnapHook creation request
        
    Returns:
        SnapHookResponse: Created SnapHook instance
    """
    logger.info(f"SnapHook CREATE request: {request.name} for cluster {request.cluster_name}")
    
    try:
        # Check if SnapHook with same name already exists
        if request.name in snaphook_instances:
            raise HTTPException(
                status_code=400,
                detail=f"SnapHook with name '{request.name}' already exists"
            )
        
        # Create ClusterConfig object from dictionary
        cluster_config = ClusterConfig(
            cluster_config_details=ClusterConfigDetails(**request.cluster_config["cluster_config_details"]),
            name=request.cluster_name
        )
        
        # Create SnapHook instance (webhook_url will be auto-generated from SNAP_API_URL)
        snaphook = SnapHook(
            cluster_name=request.cluster_name,
            cluster_config=cluster_config,
            webhook_url=request.webhook_url,  # Optional - will be auto-generated if None
            namespace=request.namespace,
            cert_expiry_days=request.cert_expiry_days
        )
        
        # Store instance
        snaphook_instances[request.name] = snaphook
        
        # Save configuration to file
        config_response = await save_snaphook_config(
            name=request.name,
            cluster_name=request.cluster_name,
            cluster_config=request.cluster_config,
            webhook_url=request.webhook_url,
            namespace=request.namespace,
            cert_expiry_days=request.cert_expiry_days
        )
        
        if not config_response.success:
            # If config save fails, remove the instance and raise error
            del snaphook_instances[request.name]
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save SnapHook configuration: {config_response.message}"
            )
        
        logger.info(f"SnapHook created: {request.name}")
        
        return SnapHookResponse(
            name=request.name,
            cluster_name=request.cluster_name,
            webhook_url=snaphook.webhook_url,
            namespace=request.namespace,
            is_running=snaphook.is_running,
            cert_expiry_days=request.cert_expiry_days,
            status=snaphook.get_status()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create SnapHook: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create SnapHook: {str(e)}"
        )


@router.get("/snaphooks", response_model=SnapHookListResponse)
async def get_snaphooks():
    """
    Get all SnapHook instances.
    
    Returns:
        SnapHookListResponse: List of SnapHook instances
    """
    try:
        snaphooks = []
        for name, snaphook in snaphook_instances.items():
            snaphooks.append(SnapHookResponse(
                name=name,
                cluster_name=snaphook.cluster_name,
                webhook_url=snaphook.webhook_url,
                namespace=snaphook.namespace,
                is_running=snaphook.is_running,
                cert_expiry_days=snaphook.cert_expiry_days,
                status=snaphook.get_status()
            ))
        
        return SnapHookListResponse(
            success=True,
            snaphooks=snaphooks,
            message=f"Found {len(snaphooks)} SnapHook instances"
        )
        
    except Exception as e:
        logger.error(f"Failed to get SnapHooks: {e}")
        return SnapHookListResponse(
            success=False,
            snaphooks=[],
            message=f"Failed to get SnapHooks: {str(e)}"
        )


@router.get("/snaphook/{hook_name}", response_model=SnapHookResponse)
async def get_snaphook(hook_name: str):
    """
    Get a specific SnapHook instance.
    
    Args:
        hook_name: Name of the SnapHook
        
    Returns:
        SnapHookResponse: SnapHook instance
    """
    try:
        if hook_name not in snaphook_instances:
            raise HTTPException(
                status_code=404,
                detail=f"SnapHook '{hook_name}' not found"
            )
        
        snaphook = snaphook_instances[hook_name]
        
        return SnapHookResponse(
            name=hook_name,
            cluster_name=snaphook.cluster_name,
            webhook_url=snaphook.webhook_url,
            namespace=snaphook.namespace,
            is_running=snaphook.is_running,
            cert_expiry_days=snaphook.cert_expiry_days,
            status=snaphook.get_status()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get SnapHook {hook_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get SnapHook: {str(e)}"
        )


@router.delete("/snaphook/{hook_name}")
async def delete_snaphook(hook_name: str):
    """
    Delete a SnapHook instance and cleanup resources.
    
    Args:
        hook_name: Name of the SnapHook to delete
        
    Returns:
        dict: Success message
    """
    try:
        if hook_name not in snaphook_instances:
            raise HTTPException(
                status_code=404,
                detail=f"SnapHook '{hook_name}' not found"
            )
        
        snaphook = snaphook_instances[hook_name]
        
        # Stop SnapHook if running
        if snaphook.is_running:
            logger.info(f"Stopping SnapHook {hook_name} before deletion")
            snaphook.stop()
        
        # Remove instance
        del snaphook_instances[hook_name]
        
        # Delete configuration file
        config_response = await delete_snaphook_config(hook_name, snaphook.cluster_name)
        if not config_response.success:
            logger.warning(f"Failed to delete SnapHook config file: {config_response.message}")
        
        logger.info(f"SnapHook deleted: {hook_name}")
        
        return {"success": True, "message": f"SnapHook '{hook_name}' deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete SnapHook {hook_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete SnapHook: {str(e)}"
        )


@router.post("/snaphook/{hook_name}/start", response_model=SnapHookResponse)
async def start_snaphook(hook_name: str):
    """
    Start a SnapHook.
    
    Args:
        hook_name: Name of the SnapHook to start
        
    Returns:
        SnapHookResponse: Updated SnapHook instance
    """
    logger.info(f"SnapHook START request: {hook_name}")
    
    try:
        if hook_name not in snaphook_instances:
            raise HTTPException(
                status_code=404,
                detail=f"SnapHook '{hook_name}' not found"
            )
        
        snaphook = snaphook_instances[hook_name]
        
        if snaphook.is_running:
            raise HTTPException(
                status_code=400,
                detail=f"SnapHook '{hook_name}' is already running"
            )
        
        # Start SnapHook
        success = snaphook.start()
        
        if success:
            # Update last_started_at timestamp in config
            await update_snaphook_config_start_time(hook_name, snaphook.cluster_name)
            logger.info(f"SnapHook started: {hook_name}")
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start SnapHook '{hook_name}'"
            )
        
        return SnapHookResponse(
            name=hook_name,
            cluster_name=snaphook.cluster_name,
            webhook_url=snaphook.webhook_url,
            namespace=snaphook.namespace,
            is_running=snaphook.is_running,
            cert_expiry_days=snaphook.cert_expiry_days,
            status=snaphook.get_status()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start SnapHook {hook_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start SnapHook: {str(e)}"
        )


@router.post("/snaphook/{hook_name}/stop", response_model=SnapHookResponse)
async def stop_snaphook(hook_name: str):
    """
    Stop a SnapHook.
    
    Args:
        hook_name: Name of the SnapHook to stop
        
    Returns:
        SnapHookResponse: Updated SnapHook instance
    """
    try:
        logger.info(f"SnapHook STOP request: {hook_name}")
        
        if hook_name not in snaphook_instances:
            raise HTTPException(
                status_code=404,
                detail=f"SnapHook '{hook_name}' not found"
            )
        
        snaphook = snaphook_instances[hook_name]
        
        if not snaphook.is_running:
            raise HTTPException(
                status_code=400,
                detail=f"SnapHook '{hook_name}' is not running"
            )
        
        # Stop SnapHook
        success = snaphook.stop()
        
        if success:
            logger.info(f"SnapHook stopped: {hook_name}")
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to stop SnapHook '{hook_name}'"
            )
        
        return SnapHookResponse(
            name=hook_name,
            cluster_name=snaphook.cluster_name,
            webhook_url=snaphook.webhook_url,
            namespace=snaphook.namespace,
            is_running=snaphook.is_running,
            cert_expiry_days=snaphook.cert_expiry_days,
            status=snaphook.get_status()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop SnapHook {hook_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop SnapHook: {str(e)}"
        )


@router.get("/snaphook/{hook_name}/status", response_model=SnapHookResponse)
async def get_snaphook_status(hook_name: str):
    """
    Get detailed status of a specific SnapHook.
    
    Args:
        hook_name: Name of the SnapHook
        
    Returns:
        SnapHookResponse: Detailed SnapHook status
    """
    try:
        if hook_name not in snaphook_instances:
            raise HTTPException(
                status_code=404,
                detail=f"SnapHook '{hook_name}' not found"
            )
        
        snaphook = snaphook_instances[hook_name]
        
        return SnapHookResponse(
            name=hook_name,
            cluster_name=snaphook.cluster_name,
            webhook_url=snaphook.webhook_url,
            namespace=snaphook.namespace,
            is_running=snaphook.is_running,
            cert_expiry_days=snaphook.cert_expiry_days,
            status=snaphook.get_status()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get SnapHook status {hook_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get SnapHook status: {str(e)}"
        )


@router.get("/snaphook/{hook_name}/test-connectivity")
async def test_snaphook_connectivity(hook_name: str):
    """
    Test SnapHook connectivity and configuration.
    
    Args:
        hook_name: Name of the SnapHook
        
    Returns:
        dict: Test results
    """
    try:
        if hook_name not in snaphook_instances:
            raise HTTPException(
                status_code=404,
                detail=f"SnapHook '{hook_name}' not found"
            )
        
        snaphook = snaphook_instances[hook_name]
        
        # Get status information
        status = snaphook.get_status()
        
        return {
            "success": True,
            "hook_name": hook_name,
            "test_results": {
                "is_running": snaphook.is_running,
                "webhook_url": snaphook.webhook_url,
                "certificate_generated": status.get("certificate_generated", False),
                "https_server_port": status.get("https_server_port"),
                "cluster_name": snaphook.cluster_name,
                "namespace": snaphook.namespace
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test connectivity for SnapHook {hook_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to test connectivity: {str(e)}"
        )


@router.get("/snaphook-configs")
async def get_snaphook_configs():
    """
    Get all saved SnapHook configurations.
    
    Returns:
        dict: List of saved SnapHook configurations
    """
    try:
        configs_response = await list_snaphook_configs()
        return configs_response
        
    except Exception as e:
        logger.error(f"Failed to get SnapHook configs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get SnapHook configs: {str(e)}"
        )
