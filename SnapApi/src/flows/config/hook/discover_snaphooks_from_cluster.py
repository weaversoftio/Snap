import logging
import os
import ssl
from typing import Dict, List, Optional
from kubernetes import client
from kubernetes.client.rest import ApiException
from flows.config.clusters.list_cluster_config import list_cluster_config
from utils.centralized_logger import log_info, log_error, log_warning

logger = logging.getLogger("automation_api")

async def discover_snaphooks_from_clusters() -> List[Dict]:
    """
    Discover existing MutatingWebhookConfigurations from all registered clusters.
    
    Returns:
        List of discovered SnapHook configurations
    """
    discovered_hooks = []
    
    try:
        log_info("Starting SnapHook discovery from clusters...", "SnapHookDiscovery")
        
        # Get all registered clusters
        cluster_configs_response = await list_cluster_config()
        
        if not cluster_configs_response.success:
            log_warning("Failed to list cluster configs for webhook discovery", "SnapHookDiscovery")
            return discovered_hooks
        
        if not cluster_configs_response.cluster_configs:
            log_info("No clusters registered, no webhooks to discover", "SnapHookDiscovery")
            return discovered_hooks
        
        # Query each cluster for MutatingWebhookConfigurations
        for cluster_config in cluster_configs_response.cluster_configs:
            try:
                cluster_name = cluster_config.name
                log_info(f"Discovering SnapHooks in cluster: {cluster_name}", "SnapHookDiscovery")
                
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
                                    
                                    log_info(f"Discovered SnapHook: {hook_name} in cluster {cluster_name}", "SnapHookDiscovery")
                
                except ApiException as e:
                    if e.status == 403:
                        log_warning(f"No permission to list webhooks in cluster {cluster_name}: {e}", "SnapHookDiscovery")
                    elif e.status == 401:
                        log_warning(f"Authentication failed for cluster {cluster_name}: {e}", "SnapHookDiscovery")
                    else:
                        log_error(f"Error querying cluster {cluster_name}: {e}", "SnapHookDiscovery")
                    continue
                    
            except Exception as e:
                log_error(f"Error discovering webhooks in cluster {cluster_config.name}: {e}", "SnapHookDiscovery")
                continue
        
        log_info(f"Discovered {len(discovered_hooks)} SnapHook configurations from clusters", "SnapHookDiscovery")
        return discovered_hooks
        
    except Exception as e:
        log_error(f"Error during webhook discovery: {e}", "SnapHookDiscovery")
        return discovered_hooks

