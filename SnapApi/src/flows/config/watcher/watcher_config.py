"""
Watcher configuration management functions.
Handles saving, loading, and managing watcher configurations.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger("automation_api")

class WatcherConfig:
    """Watcher configuration model."""
    
    def __init__(self, name: str, cluster_name: str, cluster_config: Dict[str, Any], 
                 scope: str = "cluster", trigger: str = "startupProbe", 
                 namespace: Optional[str] = None, status: str = "stopped", 
                 auto_delete_pod: bool = True):
        self.name = name
        self.cluster_name = cluster_name
        self.cluster_config = cluster_config
        self.scope = scope
        self.trigger = trigger
        self.namespace = namespace
        self.status = status
        self.auto_delete_pod = auto_delete_pod
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert watcher config to dictionary."""
        return {
            "name": self.name,
            "cluster_name": self.cluster_name,
            "cluster_config": self.cluster_config,
            "scope": self.scope,
            "trigger": self.trigger,
            "namespace": self.namespace,
            "status": self.status,
            "auto_delete_pod": self.auto_delete_pod,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WatcherConfig':
        """Create watcher config from dictionary."""
        config = cls(
            name=data["name"],
            cluster_name=data["cluster_name"],
            cluster_config=data["cluster_config"],
            scope=data.get("scope", "cluster"),
            trigger=data.get("trigger", "startupProbe"),
            namespace=data.get("namespace"),
            status=data.get("status", "stopped"),
            auto_delete_pod=data.get("auto_delete_pod", True)
        )
        config.created_at = data.get("created_at", datetime.now().isoformat())
        config.updated_at = data.get("updated_at", datetime.now().isoformat())
        return config


def save_watcher_config(watcher_config: WatcherConfig) -> bool:
    """
    Save watcher configuration to JSON file.
    
    Args:
        watcher_config: WatcherConfig instance to save
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        config_dir = "config/watcher"
        config_file = os.path.join(config_dir, f"{watcher_config.name}.json")
        
        # Ensure config directory exists
        os.makedirs(config_dir, exist_ok=True)
        
        # Update timestamp
        watcher_config.updated_at = datetime.now().isoformat()
        
        # Save to file
        with open(config_file, "w") as f:
            json.dump(watcher_config.to_dict(), f, indent=4)
        
        logger.info(f"Watcher config saved: {watcher_config.name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save watcher config {watcher_config.name}: {e}")
        return False


def load_watcher_config(watcher_name: str) -> Optional[WatcherConfig]:
    """
    Load watcher configuration from JSON file.
    
    Args:
        watcher_name: Name of the watcher config to load
        
    Returns:
        WatcherConfig instance if found, None otherwise
    """
    try:
        config_file = os.path.join("config/watcher", f"{watcher_name}.json")
        
        if not os.path.exists(config_file):
            logger.warning(f"Watcher config not found: {watcher_name}")
            return None
        
        with open(config_file, "r") as f:
            data = json.load(f)
        
        watcher_config = WatcherConfig.from_dict(data)
        logger.info(f"Watcher config loaded: {watcher_name}")
        return watcher_config
        
    except Exception as e:
        logger.error(f"Failed to load watcher config {watcher_name}: {e}")
        return None


def list_watcher_configs() -> List[WatcherConfig]:
    """
    List all watcher configurations.
    
    Returns:
        List of WatcherConfig instances
    """
    watcher_configs = []
    
    try:
        config_dir = "config/watcher"
        
        if not os.path.exists(config_dir):
            return watcher_configs
        
        for filename in os.listdir(config_dir):
            if filename.endswith(".json"):
                watcher_name = filename[:-5]  # Remove .json extension
                config = load_watcher_config(watcher_name)
                if config:
                    watcher_configs.append(config)
        
        logger.info(f"Loaded {len(watcher_configs)} watcher configs")
        
    except Exception as e:
        logger.error(f"Failed to list watcher configs: {e}")
    
    return watcher_configs


def delete_watcher_config(watcher_name: str) -> bool:
    """
    Delete watcher configuration file.
    
    Args:
        watcher_name: Name of the watcher config to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        config_file = os.path.join("config/watcher", f"{watcher_name}.json")
        
        if not os.path.exists(config_file):
            logger.warning(f"Watcher config not found for deletion: {watcher_name}")
            return False
        
        os.remove(config_file)
        logger.info(f"Watcher config deleted: {watcher_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to delete watcher config {watcher_name}: {e}")
        return False


def update_watcher_status(watcher_name: str, status: str) -> bool:
    """
    Update watcher status in configuration.
    
    Args:
        watcher_name: Name of the watcher config to update
        status: New status (running, stopped, error)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        config = load_watcher_config(watcher_name)
        if not config:
            return False
        
        config.status = status
        config.updated_at = datetime.now().isoformat()
        
        return save_watcher_config(config)
        
    except Exception as e:
        logger.error(f"Failed to update watcher status {watcher_name}: {e}")
        return False


def load_watcher_configs_on_startup() -> List[WatcherConfig]:
    """
    Load all watcher configurations on startup.
    This function should be called during application initialization.
    
    Returns:
        List of WatcherConfig instances
    """
    logger.info("Loading watcher configurations on startup...")
    configs = list_watcher_configs()
    
    if configs:
        logger.info(f"Loaded {len(configs)} watcher configurations:")
        for config in configs:
            logger.info(f"  - {config.name} (cluster: {config.cluster_name}, status: {config.status})")
    else:
        logger.info("No watcher configurations found")
    
    return configs
