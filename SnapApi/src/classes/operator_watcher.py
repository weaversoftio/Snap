"""
Integrated SnapWatcher operator functionality.
This module contains the SnapWatcherOperator class that watches for pods and triggers checkpointing.
"""

import os
import kopf
from kubernetes import client, config
from typing import Optional, Dict, Any
from classes.apirequests import PodSpecCheckpointRequest
from classes.clusterconfig import ClusterConfig
from flows.checkpoint_and_push import checkpoint_and_push_from_pod_spec
from routes.websocket import broadcast_progress
import urllib3

# Suppress urllib3 InsecureRequestWarning for Kubernetes client
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import threading


class SnapWatcherOperator:
    """
    SnapWatcher operator class that handles Kubernetes pod events and triggers checkpointing.
    Uses cluster configuration for Kubernetes client setup.
    """
    
    def __init__(self, cluster_name: str, cluster_config: ClusterConfig, scope: str = "cluster", namespace: Optional[str] = None, auto_delete_pod: bool = True):
        """
        Initialize the SnapWatcherOperator with cluster configuration.
        
        Args:
            cluster_name: Name of the cluster
            cluster_config: Cluster configuration containing API URL and token
            scope: Scope of watching - "cluster" or "namespace"
            namespace: Specific namespace to watch (required if scope is "namespace")
            auto_delete_pod: Whether to automatically delete pods after successful checkpoint
        """
        # Using print instead of logger
        self.cluster_name = cluster_name
        self.cluster_config = cluster_config
        self.scope = scope
        self.namespace = namespace
        self.auto_delete_pod = auto_delete_pod
        self.kube_client = None
        
        # Validate namespace scope
        if scope == "namespace" and not namespace:
            raise ValueError("Namespace must be specified when scope is 'namespace'")
        
        self._setup_kubernetes_config()
    
    def _setup_kubernetes_config(self) -> None:
        """Setup Kubernetes client configuration using cluster config."""
        try:
            # Create configuration object with cluster details
            kube_config = client.Configuration()
            kube_config.host = self.cluster_config.cluster_config_details.kube_api_url
            kube_config.api_key = {'authorization': f'Bearer {self.cluster_config.cluster_config_details.token}'}
            
            # SSL configuration - check environment variable for verification control
            verify_ssl = os.getenv('KUBE_VERIFY_SSL', 'false').lower() == 'true'
            kube_config.verify_ssl = verify_ssl
            
            if not verify_ssl:
                # Create SSL context that doesn't verify certificates
                import ssl
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                kube_config.ssl_ca_cert = None
                kube_config.cert_file = None
                kube_config.key_file = None
                print(f"SnapWatcher: SSL verification disabled for cluster {self.cluster_name}")
            else:
                print(f"SnapWatcher: SSL verification enabled for cluster {self.cluster_name}")
            
            # Create API client with the configuration
            self.kube_client = client.ApiClient(kube_config)
            print(f"SnapWatcher: Configured Kubernetes client for cluster {self.cluster_name}")
            
        except Exception as e:
            print(f"SnapWatcher: Could not setup Kubernetes configuration: {e}")
            raise
    
    def update_cluster_config(self, cluster_config: ClusterConfig) -> None:
        """
        Update cluster configuration for the operator.
        
        Args:
            cluster_config: New cluster configuration
        """
        self.cluster_config = cluster_config
        self._setup_kubernetes_config()
    
    def is_ready(self) -> bool:
        """Check if the operator is ready to handle events."""
        return self.kube_client is not None
    
    def delete_pod(self, pod_name: str, namespace: str) -> bool:
        """
        Delete a pod using the Kubernetes client.
        
        Args:
            pod_name: Name of the pod to delete
            namespace: Namespace of the pod
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            if not self.is_ready():
                print(f"SnapWatcher: Kubernetes client not ready, cannot delete pod {pod_name}")
                return False
            
            # Create CoreV1Api instance for pod operations
            v1 = client.CoreV1Api(self.kube_client)
            
            # Delete the pod
            v1.delete_namespaced_pod(
                name=pod_name,
                namespace=namespace,
                body=client.V1DeleteOptions()
            )
            
            print(f"SnapWatcher: Successfully initiated deletion of pod {pod_name} in namespace {namespace}")
            return True
            
        except client.exceptions.ApiException as e:
            print(f"SnapWatcher: Failed to delete pod {pod_name}: {e}")
            return False
        except Exception as e:
            print(f"SnapWatcher: Unexpected error deleting pod {pod_name}: {e}")
            return False
    
    def configure_kopf_namespace(self):
        """Configure kopf to watch specific namespace if scope is namespace."""
        if self.scope == "namespace":
            print(f"SnapWatcher: Will watch namespace: {self.namespace}")
        else:
            print(f"SnapWatcher: Will watch cluster-wide")
    
    async def handle_pod_event(self, event: Dict[str, Any], body: Dict[str, Any], logger, **kwargs) -> None:
        """
        Handle pod events for checkpointing.
        
        Args:
            event: Kubernetes event data
            body: Pod specification body
            logger: Logger instance
            **kwargs: Additional keyword arguments
        """
        if not self.is_ready():
            print("SnapWatcher: Operator not ready, skipping pod event")
            return
            
        evt_type = (event or {}).get("type") or "UNKNOWN"
        metadata = body.get("metadata", {}) or {}
        status = body.get("status", {}) or {}
        spec = body.get("spec", {}) or {}

        ns = metadata.get("namespace", "-")
        pod = metadata.get("name", "-")
        node_name = spec.get("nodeName", "-")

        # --- ignore deletions & terminating pods ---
        if evt_type == "DELETED" or metadata.get("deletionTimestamp"):
            return

        # Must be Running
        if status.get("phase") != "Running":
            return

        # Must report Ready=True
        conds = status.get("conditions", []) or []
        is_ready = any(c.get("type") == "Ready" and c.get("status") == "True" for c in conds)
        if not is_ready:
            return

        # At least one container started & running
        started = False
        for cs in status.get("containerStatuses", []) or []:
            state = cs.get("state", {}) or {}
            if "running" in state and cs.get("started"):
                started = True
                break
        if not started:
            return

        # Extract container name (first container)
        container_name = "-"
        containers = spec.get("containers") or []
        if containers:
            container_name = containers[0].get("name", "-")

        # Use broadcast for snapWatcher logs - all users will see them
        
        print(
            f"SnapWatcher: Processing checkpoint request\n"
            f"  Event:      {evt_type}\n"
            f"  Namespace:  {ns}\n"
            f"  Pod:        {pod}\n"
            f"  Container:  {container_name}\n"
            f"  Node:       {node_name}\n"
            f"  Scope:      {self.scope}"
        )

        # -----------------------------------------------------------------
        # Directly call the checkpoint function instead of HTTP request
        # -----------------------------------------------------------------
        try:
            await broadcast_progress({
                "progress": 10, 
                "task_name": "SnapWatcher Checkpoint", 
                "message": f"Starting checkpoint for pod {pod} in namespace {ns}"
            })
            
            # Prepare the complete pod specification for the request
            pod_spec_request = PodSpecCheckpointRequest(pod_spec=body)
            
            print(f"SnapWatcher: Calling checkpoint function directly for pod {pod} in cluster {self.cluster_name}")
            
            # Call the checkpoint function directly
            result = await checkpoint_and_push_from_pod_spec(pod_spec_request, self.cluster_name, "snapwatcher-operator")
            
            print(f"SnapWatcher: Checkpoint operation completed: {result.get('success', False)}")
            
            if result.get("success"):
                print(f"SnapWatcher: Checkpoint and push completed successfully for pod {pod}")
                print(f"SnapWatcher: Image tag: {result.get('image_tag', 'N/A')}")
                
                # Automatically delete the pod after successful checkpoint if enabled
                if self.auto_delete_pod:
                    await broadcast_progress({
                        "progress": 95, 
                        "task_name": "SnapWatcher Checkpoint", 
                        "message": f"Deleting pod {pod} after successful checkpoint"
                    })
                    print(f"SnapWatcher: Auto-deleting pod {pod} after successful checkpoint")
                    delete_success = self.delete_pod(pod, ns)
                    if delete_success:
                        await broadcast_progress({
                            "progress": 100, 
                            "task_name": "SnapWatcher Checkpoint", 
                            "message": f"Pod {pod} deleted successfully after checkpoint"
                        })
                        print(f"SnapWatcher: Pod {pod} deletion initiated successfully")
                    else:
                        await broadcast_progress({
                            "progress": "failed", 
                            "task_name": "SnapWatcher Checkpoint", 
                            "message": f"Failed to delete pod {pod} after checkpoint"
                        })
                        print(f"SnapWatcher: Failed to delete pod {pod}")
                else:
                    await broadcast_progress({
                        "progress": 100, 
                        "task_name": "SnapWatcher Checkpoint", 
                        "message": f"Checkpoint completed successfully for pod {pod} (auto-deletion disabled)"
                    })
                    print(f"SnapWatcher: Auto-deletion disabled, keeping pod {pod}")
            else:
                error_msg = result.get('message', 'Unknown error')
                await broadcast_progress({
                    "progress": "failed", 
                    "task_name": "SnapWatcher Checkpoint", 
                    "message": f"Checkpoint failed for pod {pod}: {error_msg}"
                })
                print(f"SnapWatcher: Checkpoint operation failed: {error_msg}")
                
        except Exception as e:
            error_msg = f"Unexpected error during checkpoint operation: {str(e)}"
            await broadcast_progress({
                "progress": "failed", 
                "task_name": "SnapWatcher Checkpoint", 
                "message": f"Checkpoint failed for pod {pod}: {error_msg}"
            })
            print(f"SnapWatcher: {error_msg}")


# Global operator instance - will be created via API request
operator: Optional[SnapWatcherOperator] = None


def set_global_operator(operator_instance: Optional[SnapWatcherOperator]):
    """Set the global operator instance for kopf event handlers."""
    global operator
    operator = operator_instance
    if operator_instance:
        # Configure kopf namespace watching
        operator_instance.configure_kopf_namespace()
        
        scope_info = f"scope: {operator_instance.scope}"
        if operator_instance.scope == "namespace":
            scope_info += f", namespace: {operator_instance.namespace}"
        print(f"SnapWatcher: Global operator set for cluster {operator_instance.cluster_name} ({scope_info})")
    else:
        print("SnapWatcher: Global operator cleared")


# Define the pod event handler using the operator instance
@kopf.on.event(
    'pods',
    labels={
        'snap.weaversoft.io/snap': kopf.PRESENT,   
        'snap.weaversoft.io/mutated': kopf.ABSENT 
    },
)
async def on_pod_event(event, body, logger, **kwargs):
    """Integrated SnapWatcher: Handle pod events for checkpointing using operator instance."""
    global operator
    if operator is None:
        print("SnapWatcher: Operator not initialized, skipping pod event")
        return
    
    # Namespace filtering for namespace scope
    if operator.scope == "namespace":
        pod_namespace = body.get("metadata", {}).get("namespace", "")
        if pod_namespace != operator.namespace:
            print(f"SnapWatcher: Skipping pod in namespace {pod_namespace} (watching {operator.namespace})")
            return
    
    await operator.handle_pod_event(event, body, logger, **kwargs)
