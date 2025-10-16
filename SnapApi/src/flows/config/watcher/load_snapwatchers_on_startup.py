"""
SnapWatcher startup loader.
Loads and starts all SnapWatcher configurations on application startup.
"""

import logging
import asyncio
from typing import Dict, Any
from classes.operator_watcher import SnapWatcherOperator
from classes.clusterconfig import ClusterConfig, ClusterConfigDetails
from flows.config.watcher.watcher_config import list_watcher_configs, load_watcher_config, update_watcher_status

logger = logging.getLogger("automation_api")

async def load_snapwatchers_on_startup(watcher_instances: Dict[str, SnapWatcherOperator]):
    """
    Load and start all SnapWatcher configurations on startup.
    
    Args:
        watcher_instances: Global dictionary to store SnapWatcher instances
    """
    try:
        logger.info("Loading SnapWatcher configurations on startup...")
        
        # Get all SnapWatcher configurations
        configs = list_watcher_configs()
        
        if not configs:
            logger.info("No SnapWatcher configurations found to load")
            return
        
        logger.info(f"Found {len(configs)} SnapWatcher configurations to load")
        
        # Load and start each SnapWatcher
        started_count = 0
        failed_count = 0
        
        for config in configs:
            try:
                name = config.name
                logger.info(f"Loading SnapWatcher: {name}")
                
                # Create ClusterConfig object from stored config
                cluster_config_dict = config.cluster_config
                cluster_config = ClusterConfig(
                    cluster_config_details=ClusterConfigDetails(**cluster_config_dict["cluster_config_details"]),
                    name=cluster_config_dict["name"]
                )
                
                # Create SnapWatcher instance
                watcher_instance = SnapWatcherOperator(
                    cluster_name=config.cluster_name,
                    cluster_config=cluster_config,
                    scope=config.scope,
                    namespace=config.namespace,
                    auto_delete_pod=config.auto_delete_pod,
                    trigger=config.trigger
                )
                
                # Store instance
                watcher_instances[name] = watcher_instance
                
                # Start the SnapWatcher if it was running before restart
                if config.status == "running":
                    logger.info(f"Starting SnapWatcher: {name}")
                    success = watcher_instance.start()
                    
                    if success:
                        # Update last_started_at timestamp
                        update_watcher_status(name, "running")
                        started_count += 1
                        logger.info(f"SnapWatcher '{name}' started successfully")
                    else:
                        failed_count += 1
                        logger.error(f"Failed to start SnapWatcher '{name}'")
                        # Update status to stopped since we couldn't start it
                        update_watcher_status(name, "stopped")
                else:
                    logger.info(f"SnapWatcher '{name}' was stopped, not auto-starting")
                
            except Exception as e:
                logger.error(f"Error loading SnapWatcher '{name}': {e}")
                failed_count += 1
                continue
        
        logger.info(f"SnapWatcher startup loading completed: {started_count} started, {failed_count} failed")
        
    except Exception as e:
        logger.error(f"Error during SnapWatcher startup loading: {e}")
