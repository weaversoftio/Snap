import logging
import asyncio
from typing import Dict, Any
from classes.snaphook import SnapHook
from classes.clusterconfig import ClusterConfig, ClusterConfigDetails
from flows.config.hook.save_snaphook_config import list_snaphook_configs, load_snaphook_config, update_snaphook_config_start_time

logger = logging.getLogger("automation_api")

async def load_snaphooks_on_startup(snaphook_instances: Dict[str, SnapHook]):
    """
    Load and start all SnapHook configurations on startup.
    
    Args:
        snaphook_instances: Global dictionary to store SnapHook instances
    """
    try:
        logger.info("Loading SnapHook configurations on startup...")
        
        # Get all SnapHook configurations
        configs_response = await list_snaphook_configs()
        
        if not configs_response["success"]:
            logger.warning(f"Failed to list SnapHook configs: {configs_response['message']}")
            return
        
        snaphook_configs = configs_response["snaphook_configs"]
        
        if not snaphook_configs:
            logger.info("No SnapHook configurations found to load")
            return
        
        logger.info(f"Found {len(snaphook_configs)} SnapHook configurations to load")
        
        # Load and start each SnapHook
        for config_data in snaphook_configs:
            try:
                name = config_data["name"]
                logger.info(f"Loading SnapHook: {name}")
                
                # Create ClusterConfig object from stored config
                cluster_config_dict = config_data["cluster_config"]
                cluster_config = ClusterConfig(
                    cluster_config_details=ClusterConfigDetails(**cluster_config_dict["cluster_config_details"]),
                    name=cluster_config_dict["name"]
                )
                
                # Get SnapHook configuration details
                snaphook_details = config_data["snaphook_config_details"]
                
                # Create SnapHook instance
                snaphook = SnapHook(
                    cluster_name=snaphook_details["cluster_name"],
                    cluster_config=cluster_config,
                    webhook_url=snaphook_details.get("webhook_url"),
                    namespace=snaphook_details.get("namespace", "snap"),
                    cert_expiry_days=snaphook_details.get("cert_expiry_days", 365)
                )
                
                # Store instance
                snaphook_instances[name] = snaphook
                
                # Start the SnapHook
                logger.info(f"Starting SnapHook: {name}")
                success = snaphook.start()
                
                if success:
                    # Update last_started_at timestamp
                    await update_snaphook_config_start_time(name, snaphook_details["cluster_name"])
                    logger.info(f"SnapHook '{name}' started successfully")
                else:
                    logger.error(f"Failed to start SnapHook '{name}'")
                
            except Exception as e:
                logger.error(f"Error loading SnapHook '{name}': {e}")
                continue
        
        logger.info("SnapHook startup loading completed")
        
    except Exception as e:
        logger.error(f"Error during SnapHook startup loading: {e}")

# Note: The synchronous wrapper has been removed as we now use the async version
# directly in FastAPI's lifespan event handler
