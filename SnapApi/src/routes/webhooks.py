"""
Dynamic Webhook Router for handling various webhook endpoints.
Allows registration of different webhook handlers dynamically.
"""

import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any, Callable, Optional, Union
import json
import asyncio
from classes.webhook_manager import webhook_manager

logger = logging.getLogger("automation_api")
router = APIRouter()

class WebhookRegistration(BaseModel):
    """Model for registering a webhook handler."""
    webhook_path: str
    handler_name: str
    description: Optional[str] = None
    handler_type: str = "generic"  # pod, registry, generic
    cluster_name: Optional[str] = None

class WebhookResponse(BaseModel):
    """Standard webhook response model."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

class WebhookHandlerResponse(BaseModel):
    """Response model for webhook handlers."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    status_code: int = 200

@router.post("/register")
async def register_webhook_handler(registration: WebhookRegistration):
    """
    Register a new webhook handler dynamically.
    
    Args:
        registration: Webhook registration details
        
    Returns:
        WebhookResponse: Registration result
    """
    try:
        success = webhook_manager.register_handler(
            name=registration.handler_name,
            path=registration.webhook_path,
            handler_type=registration.handler_type,
            description=registration.description,
            cluster_name=registration.cluster_name
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to register webhook handler for path: {registration.webhook_path}"
            )
        
        webhook_path = f"/{registration.webhook_path.lstrip('/')}"
        
        return WebhookResponse(
            success=True,
            message=f"Webhook handler '{registration.handler_name}' registered at {webhook_path}",
            data={
                "path": webhook_path, 
                "handler": registration.handler_name,
                "type": registration.handler_type,
                "cluster_name": registration.cluster_name
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to register webhook handler: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to register webhook handler: {str(e)}"
        )

@router.get("/handlers")
async def list_webhook_handlers():
    """
    List all registered webhook handlers.
    
    Returns:
        Dict: List of registered handlers
    """
    handlers = webhook_manager.list_handlers()
    return {
        "success": True,
        "handlers": [handler.dict() for handler in handlers],
        "count": len(handlers)
    }

@router.get("/handlers/{webhook_path:path}")
async def get_webhook_handler(webhook_path: str):
    """
    Get details of a specific webhook handler.
    
    Args:
        webhook_path: Path of the webhook handler
        
    Returns:
        Dict: Handler details
    """
    try:
        handler = webhook_manager.get_handler(webhook_path)
        
        if not handler:
            raise HTTPException(
                status_code=404,
                detail=f"Webhook handler not found for path: {webhook_path}"
            )
        
        return {
            "success": True,
            "handler": handler.dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get webhook handler: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get webhook handler: {str(e)}"
        )

@router.delete("/handlers/{webhook_path:path}")
async def unregister_webhook_handler(webhook_path: str):
    """
    Unregister a webhook handler.
    
    Args:
        webhook_path: Path of the webhook to unregister
        
    Returns:
        WebhookResponse: Unregistration result
    """
    try:
        handler = webhook_manager.get_handler(webhook_path)
        
        if not handler:
            raise HTTPException(
                status_code=404,
                detail=f"Webhook handler not found for path: {webhook_path}"
            )
        
        success = webhook_manager.unregister_handler(webhook_path)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to unregister webhook handler for path: {webhook_path}"
            )
        
        return WebhookResponse(
            success=True,
            message=f"Webhook handler '{handler.name}' unregistered from {handler.path}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unregister webhook handler: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to unregister webhook handler: {str(e)}"
        )

# Dynamic webhook handler - catches all POST requests to registered paths
@router.post("/{webhook_path:path}")
async def handle_dynamic_webhook(webhook_path: str, request: Request):
    """
    Handle dynamic webhook requests.
    
    Args:
        webhook_path: The webhook path
        request: FastAPI request object
        
    Returns:
        Dict: Webhook response
    """
    try:
        handler = webhook_manager.get_handler(webhook_path)
        
        if not handler:
            raise HTTPException(
                status_code=404,
                detail=f"No webhook handler registered for path: {webhook_path}"
            )
        
        if not handler.is_active:
            raise HTTPException(
                status_code=503,
                detail=f"Webhook handler is inactive for path: {webhook_path}"
            )
        
        # Get request data
        try:
            body = await request.json()
        except:
            body = await request.body()
        
        logger.info(f"Processing webhook request for {handler.name} at {handler.path}")
        print(f"🎯 DEBUG: Processing webhook request for {handler.name} at {handler.path}")
        
        # Update handler statistics
        webhook_manager.update_handler_stats(webhook_path)
        
        # Route to appropriate handler based on the webhook type
        response = await route_webhook_request(handler.path, body, request, handler)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to handle webhook request: {e}")
        print(f"💥 DEBUG: Failed to handle webhook request: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to handle webhook request: {str(e)}"
        )

async def route_webhook_request(webhook_path: str, body: Any, request: Request, handler) -> Dict[str, Any]:
    """
    Route webhook requests to appropriate handlers.
    
    Args:
        webhook_path: The webhook path
        body: Request body
        request: FastAPI request object
        handler: Handler object
        
    Returns:
        Dict: Handler response
    """
    handler_name = handler.name
    handler_type = handler.handler_type
    cluster_name = handler.cluster_name
    
    print(f"🔀 DEBUG: Routing webhook request to {handler_type} handler: {handler_name}")
    
    # Route based on handler type
    if handler_type == "pod":
        return await handle_pod_webhook(body, request, cluster_name)
    elif handler_type == "registry":
        return await handle_registry_webhook(body, request, cluster_name)
    elif handler_type == "k8s":
        return await handle_k8s_webhook(body, request, cluster_name)
    else:
        # Generic webhook handler
        return await handle_generic_webhook(body, request, handler_name, cluster_name)


async def handle_pod_webhook(body: Any, request: Request, cluster_name: Optional[str] = None) -> Dict[str, Any]:
    """Handle pod-specific webhook requests."""
    print(f"🔧 DEBUG: Handling pod webhook for cluster: {cluster_name}")
    
    try:
        # Process pod webhook data
        pod_data = body if isinstance(body, dict) else {}
        
        print(f"🔍 DEBUG: Processing pod webhook data: {pod_data}")
        logger.info(f"Pod webhook: Processing pod data for cluster {cluster_name}")
        
        return {
            "success": True,
            "message": "Pod webhook processed successfully",
            "data": {
                "cluster_name": cluster_name,
                "processed_at": asyncio.get_event_loop().time(),
                "pod_data": pod_data
            }
        }
        
    except Exception as e:
        print(f"💥 DEBUG: Pod webhook error: {e}")
        logger.error(f"Pod webhook error: {e}")
        
        return {
            "success": False,
            "message": f"Pod webhook error: {str(e)}",
            "error": str(e)
        }

async def handle_registry_webhook(body: Any, request: Request, cluster_name: Optional[str] = None) -> Dict[str, Any]:
    """Handle registry-specific webhook requests."""
    print(f"🔧 DEBUG: Handling registry webhook for cluster: {cluster_name}")
    
    try:
        # Process registry webhook data
        registry_data = body if isinstance(body, dict) else {}
        
        print(f"🔍 DEBUG: Processing registry webhook data: {registry_data}")
        logger.info(f"Registry webhook: Processing registry data for cluster {cluster_name}")
        
        return {
            "success": True,
            "message": "Registry webhook processed successfully",
            "data": {
                "cluster_name": cluster_name,
                "processed_at": asyncio.get_event_loop().time(),
                "registry_data": registry_data
            }
        }
        
    except Exception as e:
        print(f"💥 DEBUG: Registry webhook error: {e}")
        logger.error(f"Registry webhook error: {e}")
        
        return {
            "success": False,
            "message": f"Registry webhook error: {str(e)}",
            "error": str(e)
        }

async def handle_k8s_webhook(body: Any, request: Request, cluster_name: Optional[str] = None) -> Dict[str, Any]:
    """Handle Kubernetes-specific webhook requests."""
    print(f"🔧 DEBUG: Handling K8s webhook for cluster: {cluster_name}")
    
    try:
        # Process Kubernetes webhook data
        k8s_data = body if isinstance(body, dict) else {}
        
        print(f"🔍 DEBUG: Processing K8s webhook data: {k8s_data}")
        logger.info(f"K8s webhook: Processing K8s data for cluster {cluster_name}")
        
        return {
            "success": True,
            "message": "K8s webhook processed successfully",
            "data": {
                "cluster_name": cluster_name,
                "processed_at": asyncio.get_event_loop().time(),
                "k8s_data": k8s_data
            }
        }
        
    except Exception as e:
        print(f"💥 DEBUG: K8s webhook error: {e}")
        logger.error(f"K8s webhook error: {e}")
        
        return {
            "success": False,
            "message": f"K8s webhook error: {str(e)}",
            "error": str(e)
        }

async def handle_generic_webhook(body: Any, request: Request, handler_name: str, cluster_name: Optional[str] = None) -> Dict[str, Any]:
    """Handle generic webhook requests."""
    print(f"🔧 DEBUG: Handling generic webhook '{handler_name}' for cluster: {cluster_name}")
    
    try:
        # Process generic webhook data
        webhook_data = body if isinstance(body, dict) else {}
        
        print(f"🔍 DEBUG: Processing generic webhook data: {webhook_data}")
        logger.info(f"Generic webhook '{handler_name}': Processing data for cluster {cluster_name}")
        
        return {
            "success": True,
            "message": f"Generic webhook '{handler_name}' processed successfully",
            "data": {
                "handler_name": handler_name,
                "cluster_name": cluster_name,
                "processed_at": asyncio.get_event_loop().time(),
                "webhook_data": webhook_data
            }
        }
        
    except Exception as e:
        print(f"💥 DEBUG: Generic webhook error: {e}")
        logger.error(f"Generic webhook '{handler_name}' error: {e}")
        
        return {
            "success": False,
            "message": f"Generic webhook '{handler_name}' error: {str(e)}",
            "error": str(e)
        }

# Additional management endpoints
@router.get("/stats")
async def get_webhook_stats():
    """
    Get webhook statistics.
    
    Returns:
        Dict: Webhook statistics
    """
    stats = webhook_manager.get_handler_stats()
    return {
        "success": True,
        "stats": stats
    }

@router.post("/handlers/{webhook_path:path}/activate")
async def activate_webhook_handler(webhook_path: str):
    """
    Activate a webhook handler.
    
    Args:
        webhook_path: Path of the webhook handler
        
    Returns:
        WebhookResponse: Activation result
    """
    try:
        success = webhook_manager.activate_handler(webhook_path)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Webhook handler not found for path: {webhook_path}"
            )
        
        return WebhookResponse(
            success=True,
            message=f"Webhook handler activated for path: {webhook_path}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to activate webhook handler: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to activate webhook handler: {str(e)}"
        )

@router.post("/handlers/{webhook_path:path}/deactivate")
async def deactivate_webhook_handler(webhook_path: str):
    """
    Deactivate a webhook handler.
    
    Args:
        webhook_path: Path of the webhook handler
        
    Returns:
        WebhookResponse: Deactivation result
    """
    try:
        success = webhook_manager.deactivate_handler(webhook_path)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Webhook handler not found for path: {webhook_path}"
            )
        
        return WebhookResponse(
            success=True,
            message=f"Webhook handler deactivated for path: {webhook_path}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deactivate webhook handler: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to deactivate webhook handler: {str(e)}"
        )

@router.post("/cleanup")
async def cleanup_inactive_handlers(max_age_hours: int = 24):
    """
    Clean up inactive handlers older than specified age.
    
    Args:
        max_age_hours: Maximum age in hours before cleanup
        
    Returns:
        Dict: Cleanup result
    """
    try:
        cleaned_count = webhook_manager.cleanup_inactive_handlers(max_age_hours)
        
        return {
            "success": True,
            "message": f"Cleaned up {cleaned_count} inactive handlers",
            "cleaned_count": cleaned_count
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup inactive handlers: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cleanup inactive handlers: {str(e)}"
        )

# Health check endpoint
@router.get("/health")
async def webhook_health_check():
    """
    Health check endpoint for webhook router.
    
    Returns:
        Dict: Health status
    """
    stats = webhook_manager.get_handler_stats()
    return {
        "status": "healthy",
        "active_handlers": stats["active_handlers"],
        "total_handlers": stats["total_handlers"],
        "handlers": [h["path"] for h in stats["handlers"]]
    }
