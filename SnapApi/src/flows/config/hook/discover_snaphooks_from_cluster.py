import logging
import os
import ssl
from typing import Dict, List, Optional
from kubernetes import client
from kubernetes.client.rest import ApiException
from flows.config.clusters.list_cluster_config import list_cluster_config

logger = logging.getLogger("automation_api")

async def discover_snaphooks_from_clusters() -> List[Dict]:
    """
    Discover existing MutatingWebhookConfigurations from all registered clusters.
    
    Returns:
        List of discovered SnapHook configurations
    """
    discovered_hooks = []
    
    try:
        logger.info("[SnapHookDiscovery] Starting SnapHook discovery from clusters...")
        
        # Get all registered clusters
        cluster_configs_response = await list_cluster_config()
        
        if not cluster_configs_response.success:
            logger.warning("[SnapHookDiscovery] Failed to list cluster configs for webhook discovery")
            return discovered_hooks
        
        if not cluster_configs_response.cluster_configs:
            logger.info("[SnapHookDiscovery] No clusters registered, no webhooks to discover")
            return discovered_hooks
        
        # Query each cluster for MutatingWebhookConfigurations
        for cluster_config in cluster_configs_response.cluster_configs:
            try:
                cluster_name = cluster_config.name
                logger.info(f"[SnapHookDiscovery] Discovering SnapHooks in cluster: {cluster_name}")
                
                # Setup Kubernetes client for this cluster
                kube_config = client.Configuration()
                kube_config.host = cluster_config.cluster_config_details.kube_api_url
                kube_config.api_key = {
                    'authorization': f'Bearer {cluster_config.cluster_config_details.token}'
                }
                
                # SSL configuration
                verify_ssl = os.getenv('KUBE_VERIFY_SSL', 'false').lower() == 'true'
                kube_config.verify_ssl = verify_ssl
                
                if not verify_ssl:
                    ssl_context = ssl.create_default_context()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                    kube_config.ssl_ca_cert = None
                    kube_config.cert_file = None
                    kube_config.key_file = None
                
                kube_client = client.ApiClient(kube_config)
                admission_v1 = client.AdmissionregistrationV1Api(kube_client)
                
                # List all MutatingWebhookConfigurations
                try:
                    webhook_configs = admission_v1.list_mutating_webhook_configuration()
                    
                    # Filter for SnapHook webhooks (by label selector)
                    for webhook_config in webhook_configs.items:
                        labels = webhook_config.metadata.labels or {}
                        
                        # Check if this is a SnapHook webhook
                        if labels.get("app") == "snaphook" and labels.get("managed-by") == "snapapi":
                            hook_name = labels.get("hook-name")
                            webhook_cluster = labels.get("cluster-name")
                            
                            if hook_name and webhook_cluster == cluster_name:
                                # Extract webhook details
                                if webhook_config.webhooks and len(webhook_config.webhooks) > 0:
                                    webhook = webhook_config.webhooks[0]
                                    webhook_url = webhook.client_config.url
                                    ca_bundle = webhook.client_config.ca_bundle
                                    
                                    discovered_hooks.append({
                                        "name": hook_name,
                                        "cluster_name": cluster_name,
                                        "cluster_config": {
                                            "name": cluster_name,
                                            "cluster_config_details": {
                                                "kube_api_url": cluster_config.cluster_config_details.kube_api_url,
                                                "token": cluster_config.cluster_config_details.token
                                            }
                                        },
                                        "webhook_url": webhook_url,
                                        "namespace": labels.get("namespace", "snap"),
                                        "cert_expiry_days": 365,  # Default, can't determine from cluster
                                        "webhook_config_name": webhook_config.metadata.name,
                                        "ca_bundle": ca_bundle,
                                        "exists_in_cluster": True
                                    })
                                    
                                    logger.info(f"[SnapHookDiscovery] Discovered SnapHook: {hook_name} in cluster {cluster_name}")
                
                except ApiException as e:
                    if e.status == 403:
                        logger.warning(f"[SnapHookDiscovery] No permission to list webhooks in cluster {cluster_name}: {e}")
                    elif e.status == 401:
                        logger.warning(f"[SnapHookDiscovery] Authentication failed for cluster {cluster_name}: {e}")
                    else:
                        logger.error(f"[SnapHookDiscovery] Error querying cluster {cluster_name}: {e}")
                    continue
                    
            except Exception as e:
                logger.error(f"[SnapHookDiscovery] Error discovering webhooks in cluster {cluster_config.name}: {e}")
                continue
        
        logger.info(f"[SnapHookDiscovery] Discovered {len(discovered_hooks)} SnapHook configurations from clusters")
        return discovered_hooks
        
    except Exception as e:
        logger.error(f"[SnapHookDiscovery] Error during webhook discovery: {e}")
        return discovered_hooks

