import logging
from typing import Dict, Any
from classes.snaphook import SnapHook
from classes.clusterconfig import ClusterConfig, ClusterConfigDetails
from flows.config.hook.discover_snaphooks_from_cluster import discover_snaphooks_from_clusters
from flows.config.hook.hook_utils import is_certificate_valid, verify_certificate_matches_server, sync_hook_to_config

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
                
                # Check if certificate is valid and matches server
                ca_bundle = hook_data.get("ca_bundle")
                cert_valid = is_certificate_valid(ca_bundle)
                cert_matches = False
                cert_fixed = False
                
                # First ensure shared HTTPS server is running before checking certificate match
                from classes.shared_https_server import shared_https_server
                if not shared_https_server.is_running:
                    logger.info(f"[SnapHookStartup] Starting shared HTTPS server for certificate verification...")
                    if not shared_https_server.start_shared_server():
                        logger.error(f"[SnapHookStartup] Failed to start shared HTTPS server")
                
                # Check if certificate matches the server (detects certificate mismatches)
                if cert_valid and shared_https_server.is_running:
                    cert_matches = verify_certificate_matches_server(ca_bundle)
                    if not cert_matches:
                        logger.warning(
                            f"[SnapHookStartup] Certificate mismatch detected for hook '{name}'! "
                            f"The CA bundle in the webhook doesn't match the certificate being served. "
                            f"This will cause 'certificate signed by unknown authority' errors. Fixing automatically..."
                        )
                
                if not cert_valid or not cert_matches:
                    logger.warning(f"[SnapHookStartup] Certificate for hook '{name}' needs fixing (valid: {cert_valid}, matches: {cert_matches}), updating webhook...")
                    # Fix the hook by updating webhook with current server certificate
                    try:
                        # Start the hook which will update the webhook with current CA bundle from server
                        if snaphook.start():
                            logger.info(f"[SnapHookStartup] Successfully fixed hook '{name}' certificate (updated webhook with server certificate)")
                            cert_fixed = True
                        else:
                            logger.error(f"[SnapHookStartup] Failed to fix hook '{name}' certificate")
                    except Exception as e:
                        logger.error(f"[SnapHookStartup] Error fixing hook '{name}' certificate: {e}")
                        import traceback
                        logger.error(f"[SnapHookStartup] Traceback: {traceback.format_exc()}")
                else:
                    logger.info(f"[SnapHookStartup] Certificate for hook '{name}' is valid and matches server certificate")
                
                # Store instance
                snaphook_instances[name] = snaphook
                
                # Register handler with shared server (webhook already exists in cluster)
                if cert_fixed:
                    # Certificate was fixed and hook was started, so it's already registered
                    logger.info(f"[SnapHookStartup] SnapHook '{name}' already registered (certificate was fixed)")
                elif shared_https_server.is_running:
                    # Register handler but don't recreate webhook config (webhook already exists in cluster)
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
                
                # Sync hook to config folder for backup
                try:
                    await sync_hook_to_config(
                        name=name,
                        cluster_name=cluster_name,
                        cluster_config=hook_data["cluster_config"],
                        webhook_url=hook_data.get("webhook_url"),
                        namespace=hook_data.get("namespace", "snap"),
                        cert_expiry_days=hook_data.get("cert_expiry_days", 365)
                    )
                    logger.info(f"[SnapHookStartup] Synced hook '{name}' to config folder for backup")
                except Exception as e:
                    logger.error(f"[SnapHookStartup] Failed to sync hook '{name}' to config folder: {e}")
                
            except Exception as e:
                logger.error(f"[SnapHookStartup] Error loading discovered SnapHook '{hook_data.get('name', 'unknown')}': {e}")
                continue
        
        logger.info(f"[SnapHookStartup] SnapHook startup discovery completed - {len(discovered_hooks)} hooks loaded")
        
    except Exception as e:
        logger.error(f"[SnapHookStartup] Error during SnapHook startup discovery: {e}")

# Note: The synchronous wrapper has been removed as we now use the async version
# directly in FastAPI's lifespan event handler
