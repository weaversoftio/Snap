import logging
from typing import Dict, Any
from classes.snaphook import SnapHook
from classes.clusterconfig import ClusterConfig, ClusterConfigDetails
from flows.config.hook.discover_snaphooks_from_cluster import discover_snaphooks_from_clusters

logger = logging.getLogger("automation_api")

async def load_snaphooks_on_startup(snaphook_instances: Dict[str, SnapHook]):
    """
    Discover and load SnapHook configurations from clusters on startup.
    Only loads webhooks that actually exist in the cluster.
    Configuration persistence is now in the cluster itself, not on disk.
    
    Args:
        snaphook_instances: Global dictionary to store SnapHook instances
    """
    try:
        logger.info("[SnapHookStartup] Discovering SnapHook configurations from clusters...")
        
        # Discover webhooks from all clusters
        discovered_hooks = await discover_snaphooks_from_clusters()
        
        if not discovered_hooks:
            logger.info("[SnapHookStartup] No SnapHook configurations found in clusters")
            return
        
        logger.info(f"[SnapHookStartup] Found {len(discovered_hooks)} SnapHook configurations in clusters")
        
        # Load each discovered SnapHook
        for hook_data in discovered_hooks:
            try:
                name = hook_data["name"]
                cluster_name = hook_data["cluster_name"]
                
                logger.info(f"[SnapHookStartup] Loading discovered SnapHook: {name} for cluster {cluster_name}")
                
                # Create ClusterConfig object
                cluster_config_dict = hook_data["cluster_config"]
                cluster_config = ClusterConfig(
                    cluster_config_details=ClusterConfigDetails(**cluster_config_dict["cluster_config_details"]),
                    name=cluster_config_dict["name"]
                )
                
                # Create SnapHook instance
                snaphook = SnapHook(
                    name=name,
                    cluster_name=cluster_name,
                    cluster_config=cluster_config,
                    webhook_url=hook_data.get("webhook_url"),
                    namespace=hook_data.get("namespace", "snap"),
                    cert_expiry_days=hook_data.get("cert_expiry_days", 365)
                )
                
                # Store the CA bundle from the existing webhook
                if hook_data.get("ca_bundle"):
                    snaphook.ca_bundle = hook_data["ca_bundle"]
                
                # Store instance
                snaphook_instances[name] = snaphook
                
                # Register handler with shared server (webhook already exists in cluster)
                from classes.shared_https_server import shared_https_server
                if shared_https_server.is_running:
                    # Register handler but don't recreate webhook config
                    shared_https_server.register_hook_handler(name, snaphook._create_webhook_handler())
                    snaphook.is_running = True
                    logger.info(f"[SnapHookStartup] SnapHook '{name}' registered with shared server (already exists in cluster)")
                else:
                    logger.warning(f"[SnapHookStartup] Shared HTTPS server not running, cannot register SnapHook '{name}'")
                    # Try to start the shared server
                    if shared_https_server.start_shared_server():
                        shared_https_server.register_hook_handler(name, snaphook._create_webhook_handler())
                        snaphook.is_running = True
                        logger.info(f"[SnapHookStartup] SnapHook '{name}' registered after starting shared server")
                    else:
                        logger.error(f"[SnapHookStartup] Failed to start shared HTTPS server, cannot register SnapHook '{name}'")
                
            except Exception as e:
                logger.error(f"[SnapHookStartup] Error loading discovered SnapHook '{hook_data.get('name', 'unknown')}': {e}")
                continue
        
        logger.info(f"[SnapHookStartup] SnapHook startup discovery completed - {len(discovered_hooks)} hooks loaded")
        
    except Exception as e:
        logger.error(f"[SnapHookStartup] Error during SnapHook startup discovery: {e}")

# Note: The synchronous wrapper has been removed as we now use the async version
# directly in FastAPI's lifespan event handler
