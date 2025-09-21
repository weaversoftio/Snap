"""
Webhook Manager for dynamic webhook registration and management.
Handles registration, routing, and lifecycle management of webhook handlers.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from pydantic import BaseModel

logger = logging.getLogger("automation_api")

class WebhookHandler(BaseModel):
    """Model for webhook handler information."""
    name: str
    path: str
    handler_type: str
    description: Optional[str] = None
    cluster_name: Optional[str] = None
    registered_at: float
    is_active: bool = True
    call_count: int = 0
    last_called: Optional[float] = None

class WebhookManager:
    """Manages dynamic webhook handlers and routing."""
    
    def __init__(self):
        """Initialize WebhookManager."""
        self.handlers: Dict[str, WebhookHandler] = {}
        self.handler_functions: Dict[str, Callable] = {}
        self.logger = logging.getLogger("automation_api")
    
    def register_handler(self, 
                        name: str, 
                        path: str, 
                        handler_type: str = "generic",
                        description: Optional[str] = None,
                        cluster_name: Optional[str] = None,
                        handler_function: Optional[Callable] = None) -> bool:
        """
        Register a new webhook handler.
        
        Args:
            name: Handler name
            path: Webhook path
            handler_type: Type of handler (pod, registry, generic)
            description: Handler description
            cluster_name: Associated cluster name
            handler_function: Optional custom handler function
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Normalize path
            normalized_path = f"/{path.lstrip('/')}"
            
            if normalized_path in self.handlers:
                self.logger.warning(f"Handler already exists for path: {normalized_path}")
                return False
            
            # Create handler info
            handler = WebhookHandler(
                name=name,
                path=normalized_path,
                handler_type=handler_type,
                description=description,
                cluster_name=cluster_name,
                registered_at=asyncio.get_event_loop().time(),
                is_active=True,
                call_count=0
            )
            
            # Store handler
            self.handlers[normalized_path] = handler
            
            # Store custom handler function if provided
            if handler_function:
                self.handler_functions[normalized_path] = handler_function
            
            self.logger.info(f"Registered webhook handler: {name} at {normalized_path}")
            print(f"🔧 DEBUG: Registered webhook handler: {name} at {normalized_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to register webhook handler: {e}")
            return False
    
    def unregister_handler(self, path: str) -> bool:
        """
        Unregister a webhook handler.
        
        Args:
            path: Webhook path
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            normalized_path = f"/{path.lstrip('/')}"
            
            if normalized_path not in self.handlers:
                self.logger.warning(f"Handler not found for path: {normalized_path}")
                return False
            
            handler_info = self.handlers.pop(normalized_path)
            
            # Remove custom handler function if exists
            if normalized_path in self.handler_functions:
                del self.handler_functions[normalized_path]
            
            self.logger.info(f"Unregistered webhook handler: {handler_info.name} from {normalized_path}")
            print(f"🗑️ DEBUG: Unregistered webhook handler: {handler_info.name} from {normalized_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to unregister webhook handler: {e}")
            return False
    
    def get_handler(self, path: str) -> Optional[WebhookHandler]:
        """
        Get handler information for a path.
        
        Args:
            path: Webhook path
            
        Returns:
            WebhookHandler or None if not found
        """
        normalized_path = f"/{path.lstrip('/')}"
        return self.handlers.get(normalized_path)
    
    def list_handlers(self) -> List[WebhookHandler]:
        """
        List all registered handlers.
        
        Returns:
            List of WebhookHandler objects
        """
        return list(self.handlers.values())
    
    def get_handlers_by_type(self, handler_type: str) -> List[WebhookHandler]:
        """
        Get handlers by type.
        
        Args:
            handler_type: Type of handlers to filter
            
        Returns:
            List of matching WebhookHandler objects
        """
        return [handler for handler in self.handlers.values() 
                if handler.handler_type == handler_type]
    
    def get_handlers_by_cluster(self, cluster_name: str) -> List[WebhookHandler]:
        """
        Get handlers by cluster name.
        
        Args:
            cluster_name: Cluster name to filter
            
        Returns:
            List of matching WebhookHandler objects
        """
        return [handler for handler in self.handlers.values() 
                if handler.cluster_name == cluster_name]
    
    def update_handler_stats(self, path: str) -> bool:
        """
        Update handler statistics.
        
        Args:
            path: Webhook path
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            normalized_path = f"/{path.lstrip('/')}"
            
            if normalized_path not in self.handlers:
                return False
            
            handler = self.handlers[normalized_path]
            handler.call_count += 1
            handler.last_called = asyncio.get_event_loop().time()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update handler stats: {e}")
            return False
    
    def deactivate_handler(self, path: str) -> bool:
        """
        Deactivate a handler without removing it.
        
        Args:
            path: Webhook path
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            normalized_path = f"/{path.lstrip('/')}"
            
            if normalized_path not in self.handlers:
                return False
            
            self.handlers[normalized_path].is_active = False
            self.logger.info(f"Deactivated webhook handler: {normalized_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to deactivate handler: {e}")
            return False
    
    def activate_handler(self, path: str) -> bool:
        """
        Activate a handler.
        
        Args:
            path: Webhook path
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            normalized_path = f"/{path.lstrip('/')}"
            
            if normalized_path not in self.handlers:
                return False
            
            self.handlers[normalized_path].is_active = True
            self.logger.info(f"Activated webhook handler: {normalized_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to activate handler: {e}")
            return False
    
    def get_handler_stats(self) -> Dict[str, Any]:
        """
        Get overall handler statistics.
        
        Returns:
            Dict containing statistics
        """
        total_handlers = len(self.handlers)
        active_handlers = len([h for h in self.handlers.values() if h.is_active])
        total_calls = sum(h.call_count for h in self.handlers.values())
        
        handler_types = {}
        for handler in self.handlers.values():
            handler_type = handler.handler_type
            if handler_type not in handler_types:
                handler_types[handler_type] = 0
            handler_types[handler_type] += 1
        
        return {
            "total_handlers": total_handlers,
            "active_handlers": active_handlers,
            "inactive_handlers": total_handlers - active_handlers,
            "total_calls": total_calls,
            "handler_types": handler_types,
            "handlers": [
                {
                    "name": h.name,
                    "path": h.path,
                    "type": h.handler_type,
                    "cluster_name": h.cluster_name,
                    "is_active": h.is_active,
                    "call_count": h.call_count,
                    "last_called": h.last_called
                }
                for h in self.handlers.values()
            ]
        }
    
    def cleanup_inactive_handlers(self, max_age_hours: int = 24) -> int:
        """
        Clean up inactive handlers older than specified age.
        
        Args:
            max_age_hours: Maximum age in hours before cleanup
            
        Returns:
            int: Number of handlers cleaned up
        """
        try:
            current_time = asyncio.get_event_loop().time()
            max_age_seconds = max_age_hours * 3600
            
            handlers_to_remove = []
            
            for path, handler in self.handlers.items():
                if not handler.is_active:
                    age_seconds = current_time - handler.registered_at
                    if age_seconds > max_age_seconds:
                        handlers_to_remove.append(path)
            
            for path in handlers_to_remove:
                self.unregister_handler(path)
            
            self.logger.info(f"Cleaned up {len(handlers_to_remove)} inactive handlers")
            return len(handlers_to_remove)
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup inactive handlers: {e}")
            return 0

# Global webhook manager instance
webhook_manager = WebhookManager()
