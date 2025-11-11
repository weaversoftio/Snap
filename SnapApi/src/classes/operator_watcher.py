"""
Integrated SnapWatcher operator functionality.
This module contains the SnapWatcherOperator class that watches for pods and triggers checkpointing.
"""

import os
import logging
import asyncio
import threading
import time
from kubernetes import client, watch
from typing import Optional, Dict, Any
from classes.apirequests import PodSpecCheckpointRequest
from classes.clusterconfig import ClusterConfig
from flows.checkpoint_and_push import checkpoint_and_push_from_pod_spec
from routes.websocket import broadcast_progress
from utils.centralized_logger import log_info, log_error, log_warning, log_success

# Setup logger for SnapWatcher
logger = logging.getLogger("automation_api.SnapWatcher")


class SnapWatcherOperator:
    """
    SnapWatcher operator class that handles Kubernetes pod events and triggers checkpointing.
    Uses cluster configuration for Kubernetes client setup.
    """
    
    def __init__(self, cluster_name: str, cluster_config: ClusterConfig, scope: str = "cluster", namespace: Optional[str] = None, auto_delete_pod: bool = True, trigger: str = "startupProbe"):
        """
        Initialize the SnapWatcherOperator with cluster configuration.
        
        Args:
            cluster_name: Name of the cluster
            cluster_config: Cluster configuration containing API URL and token
            scope: Scope of watching - "cluster" or "namespace"
            namespace: Specific namespace to watch (required if scope is "namespace")
            auto_delete_pod: Whether to automatically delete pods after successful checkpoint
            trigger: Trigger type for checkpointing - "startupProbe" or "always"
        """
        # Using proper logging instead of print
        self.cluster_name = cluster_name
        self.cluster_config = cluster_config
        self.scope = scope
        self.namespace = namespace
        self.auto_delete_pod = auto_delete_pod
        self.trigger = trigger
        self.kube_client = None
        self.is_running = False
        self.watch_thread = None
        self._stop_event = threading.Event()
        
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
                log_info(f'SSL verification disabled for cluster {self.cluster_name}', 'SnapWatcher')
            else:
                log_info(f'SSL verification enabled for cluster {self.cluster_name}', 'SnapWatcher')
            
            # Create API client with the configuration
            self.kube_client = client.ApiClient(kube_config)
            log_info(f'Configured Kubernetes client for cluster {self.cluster_name}', 'SnapWatcher')
            
        except Exception as e:
            log_error(f'Could not setup Kubernetes configuration: {e}', 'SnapWatcher')
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
    
    def is_actually_running(self) -> bool:
        """
        Check if the watcher is actually running by verifying both the flag and thread status.
        
        Returns:
            bool: True if watcher is running and thread is alive, False otherwise
        """
        if not self.is_running:
            return False
        # Check if thread exists and is alive
        if self.watch_thread is None:
            return False
        if not self.watch_thread.is_alive():
            # Thread is dead but flag is True - fix the state
            self.is_running = False
            return False
        return True
    
    def start(self) -> bool:
        """
        Start the SnapWatcherOperator by beginning to watch for pods.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.is_ready():
                log_error(f'Kubernetes client not ready, cannot start watcher', 'SnapWatcher')
                return False
            
            if self.is_running:
                log_warning(f'Watcher is already running', 'SnapWatcher')
                return True
            
            log_info(f'Starting SnapWatcher for cluster {self.cluster_name}', 'SnapWatcher')
            
            # Reset stop event
            self._stop_event.clear()
            
            # Start watch thread
            self.watch_thread = threading.Thread(target=self._watch_pods, daemon=True)
            self.watch_thread.start()
            
            self.is_running = True
            log_success(f'SnapWatcher started successfully for cluster {self.cluster_name}', 'SnapWatcher')
            return True
            
        except Exception as e:
            log_error(f'Failed to start SnapWatcher: {e}', 'SnapWatcher')
            self.is_running = False
            return False
    
    def stop(self) -> bool:
        """
        Stop the SnapWatcherOperator.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.is_running:
                log_warning(f'Watcher is not running', 'SnapWatcher')
                return True
            
            log_info(f'Stopping SnapWatcher for cluster {self.cluster_name}', 'SnapWatcher')
            
            # Signal stop event
            self._stop_event.set()
            
            # Wait for watch thread to finish
            if self.watch_thread and self.watch_thread.is_alive():
                self.watch_thread.join(timeout=10)  # Wait up to 10 seconds
            
            self.is_running = False
            self.watch_thread = None
            
            log_success(f'SnapWatcher stopped successfully for cluster {self.cluster_name}', 'SnapWatcher')
            return True
            
        except Exception as e:
            log_error(f'Failed to stop SnapWatcher: {e}', 'SnapWatcher')
            return False
    
    def _watch_pods(self) -> None:
        """
        Watch for pod events using Kubernetes watch API.
        This method runs in a separate thread and automatically restarts on timeout/errors.
        """
        while not self._stop_event.is_set():
            try:
                v1 = client.CoreV1Api(self.kube_client)
                w = watch.Watch()
                
                # Configure label selector to filter at Kubernetes API level
                # Include pods with snap=true but exclude pods with mutated=true
                label_selector = "snap.weaversoft.io/snap=true,!snap.weaversoft.io/mutated"
                
                # Configure watch parameters based on scope with label filtering
                if self.scope == "namespace":
                    log_info(f'Watching pods in namespace: {self.namespace} with label selector: {label_selector}', 'SnapWatcher')
                    stream = w.stream(v1.list_namespaced_pod, namespace=self.namespace, label_selector=label_selector, timeout_seconds=60)
                else:
                    log_info(f'Watching pods cluster-wide with label selector: {label_selector}', 'SnapWatcher')
                    stream = w.stream(v1.list_pod_for_all_namespaces, label_selector=label_selector, timeout_seconds=60)
                
                for event in stream:
                    # Check if we should stop
                    if self._stop_event.is_set():
                        log_info(f'Stop event received, exiting watch loop', 'SnapWatcher')
                        break
                    
                    
                    # Process the event
                    try:
                        # Run the async function directly in this thread
                        asyncio.run(self._process_pod_event(event))
                    except Exception as e:
                        log_error(f'Error processing pod event in watch loop: {e}', 'SnapWatcher')
                
                # Watch stream ended (timeout or connection closed)
                # If we're not stopping, restart the watch loop
                if not self._stop_event.is_set():
                    log_info(f'Watch stream ended, restarting watch loop for cluster {self.cluster_name}', 'SnapWatcher')
                    # Small delay before restarting to avoid tight loop
                    time.sleep(1)
                
            except Exception as e:
                if not self._stop_event.is_set():  # Only log if not stopping
                    log_error(f'Error in watch loop: {e}', 'SnapWatcher')
                    # Small delay before retrying to avoid tight loop
                    time.sleep(5)
                else:
                    # We're stopping, break out of the loop
                    break
        
        # Thread is exiting - update is_running flag
        self.is_running = False
        log_info(f'Watch thread exiting for cluster {self.cluster_name}', 'SnapWatcher')
    
    async def _process_pod_event(self, event) -> None:
        """
        Process a pod event from the watch stream.
        
        Args:
            event: Kubernetes watch event
        """
        try:
            event_type = event['type']
            pod_body = event['object']
            
            
            # Convert V1Pod object to dictionary format expected by handle_pod_event
            if hasattr(pod_body, 'to_dict'):
                pod_dict = pod_body.to_dict()
            else:
                # Fallback: convert to dict manually using the V1Pod attributes
                pod_dict = {
                    'metadata': pod_body.metadata.to_dict() if pod_body.metadata else {},
                    'spec': pod_body.spec.to_dict() if pod_body.spec else {},
                    'status': pod_body.status.to_dict() if pod_body.status else {}
                }
            
            # Convert to the format expected by handle_pod_event
            event_dict = {'type': event_type}
            
            # Call the existing handle_pod_event method
            await self.handle_pod_event(event_dict, pod_dict, logger)
            
        except Exception as e:
            log_error(f'Error processing pod event: {e}', 'SnapWatcher')
    
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
                log_warning(f'Kubernetes client not ready, cannot delete pod {pod_name}', 'SnapWatcher')
                return False
                
            # Create CoreV1Api instance for pod operations
            v1 = client.CoreV1Api(self.kube_client)
            
            # Delete the pod
            v1.delete_namespaced_pod(
                name=pod_name,
                namespace=namespace,
                body=client.V1DeleteOptions()
            )
            
            log_success(f'Successfully initiated deletion of pod {pod_name} in namespace {namespace}', 'SnapWatcher')
            return True
            
        except client.exceptions.ApiException as e:
            log_error(f'Failed to delete pod {pod_name}: {e}', 'SnapWatcher')
            return False
        except Exception as e:
            log_error(f'Unexpected error deleting pod {pod_name}: {e}', 'SnapWatcher')
            return False
    
    
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
            log_warning(f'Operator not ready, skipping pod event', 'SnapWatcher')
            return
            
        evt_type = (event or {}).get("type") or "UNKNOWN"
        metadata = body.get("metadata", {}) or {}
        status = body.get("status", {}) or {}
        spec = body.get("spec", {}) or {}

        ns = metadata.get("namespace", "-")
        pod = metadata.get("name", "-")
        node_name = spec.get("node_name", "-")  # Use node_name instead of nodeName
        labels = metadata.get("labels", {}) or {}
        containers = spec.get("containers", []) or []

        # --- ignore deletions & terminating pods ---
        if evt_type == "DELETED" or metadata.get("deletionTimestamp"):
            return

        # Must be Running
        if status.get("phase") != "Running":
            return

        # --- Check startup probe filter (when startup probe is selected) ---
        if self.trigger == "startupProbe":
            # For startup probe trigger, we wait for pods to be ready (startup probe passed)
            # This means we only checkpoint pods that have successfully completed their startup probe
            # Must report Ready=True
            conds = status.get("conditions", []) or []
            is_ready = any(c.get("type") == "Ready" and c.get("status") == "True" for c in conds)
            if not is_ready:
                return

        # At least one container started & running
        started = False
        container_statuses = status.get("container_statuses", []) or []

        for cs in container_statuses:
            state = cs.get("state", {}) or {}
            started_flag = cs.get("started", False)

            # Check if container is running and started
            # The 'started' field might not always be present, so we also check if the container is actually running
            if "running" in state and (started_flag or state.get("running")):
                started = True
                break
        
        if not started:
            return

        # Extract container name (first container)
        container_name = "-"
        containers = spec.get("containers") or []
        if containers:
            container_name = containers[0].get("name", "-")

        # Log that this pod meets all criteria for checkpointing
        log_info(f'Pod {pod} meets all criteria for checkpointing - Event: {evt_type}, Namespace: {ns}, Container: {container_name}, Node: {node_name}, Scope: {self.scope}', 'SnapWatcher')

        # Use broadcast for snapWatcher logs - all users will see them
        
        log_info(f'Processing checkpoint request - Event: {evt_type}, Namespace: {ns}, Pod: {pod}, Container: {container_name}, Node: {node_name}, Scope: {self.scope}', 'SnapWatcher')

        # -----------------------------------------------------------------
        # Directly call the checkpoint function instead of HTTP request
        # -----------------------------------------------------------------
        try:
            self._safe_broadcast_progress({
                "progress": 10, 
                "task_name": "SnapWatcher Checkpoint", 
                "message": f"Starting checkpoint for pod {pod} in namespace {ns}"
            })
            
            # Prepare the complete pod specification for the request
            pod_spec_request = PodSpecCheckpointRequest(pod_spec=body)
            
            log_info(f'Calling checkpoint function directly for pod {pod} in cluster {self.cluster_name}', 'SnapWatcher')
            
            # Call the checkpoint function directly
            result = await checkpoint_and_push_from_pod_spec(pod_spec_request, self.cluster_name, "snapwatcher-operator")
            
            log_info(f'Checkpoint operation completed: {result.get("success", False)}', 'SnapWatcher')
            
            if result.get("success"):
                log_success(f'Checkpoint and push completed successfully for pod {pod}', 'SnapWatcher')
                log_info(f'Image tag: {result.get("image_tag", "N/A")}', 'SnapWatcher')
                
                # Automatically delete the pod after successful checkpoint if enabled
                if self.auto_delete_pod:
                    await broadcast_progress({
                        "progress": 95, 
                        "task_name": "SnapWatcher Checkpoint", 
                        "message": f"Deleting pod {pod} after successful checkpoint"
                    })
                    log_info(f'Auto-deleting pod {pod} after successful checkpoint', 'SnapWatcher')
                    delete_success = self.delete_pod(pod, ns)
                    if delete_success:
                        self._safe_broadcast_progress({
                            "progress": 100, 
                            "task_name": "SnapWatcher Checkpoint", 
                            "message": f"Pod {pod} deleted successfully after checkpoint"
                        })
                        log_success(f'Pod {pod} deletion initiated successfully', 'SnapWatcher')
                    else:
                        self._safe_broadcast_progress({
                            "progress": "failed", 
                            "task_name": "SnapWatcher Checkpoint", 
                            "message": f"Failed to delete pod {pod} after checkpoint"
                        })
                        log_error(f'Failed to delete pod {pod}', 'SnapWatcher')
                else:
                    self._safe_broadcast_progress({
                        "progress": 100, 
                        "task_name": "SnapWatcher Checkpoint", 
                        "message": f"Checkpoint completed successfully for pod {pod} (auto-deletion disabled)"
                    })
                    log_info(f'Auto-deletion disabled, keeping pod {pod}', 'SnapWatcher')
            else:
                error_msg = result.get('message', 'Unknown error')
                self._safe_broadcast_progress({
                    "progress": "failed", 
                    "task_name": "SnapWatcher Checkpoint", 
                    "message": f"Checkpoint failed for pod {pod}: {error_msg}"
                })
                log_error(f'Checkpoint operation failed: {error_msg}', 'SnapWatcher')
                
        except Exception as e:
            error_msg = f"Unexpected error during checkpoint operation: {str(e)}"
            self._safe_broadcast_progress({
                "progress": "failed", 
                "task_name": "SnapWatcher Checkpoint", 
                "message": f"Checkpoint failed for pod {pod}: {error_msg}"
            })
            log_error(error_msg, 'SnapWatcher')


    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of SnapWatcherOperator.
        
        Returns:
            Dict containing status information
        """
        return {
            "cluster_name": self.cluster_name,
            "scope": self.scope,
            "namespace": self.namespace,
            "auto_delete_pod": self.auto_delete_pod,
            "trigger": self.trigger,
            "is_ready": self.is_ready(),
            "is_running": getattr(self, 'is_running', False),
            "watch_thread_alive": getattr(self, 'watch_thread', None) is not None and getattr(self, 'watch_thread', None).is_alive() if hasattr(self, 'watch_thread') else False
        }
    
    def _safe_broadcast_progress(self, data: dict) -> None:
        """Safely broadcast progress from SnapWatcher thread to main event loop."""
        try:
            # Get the main event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule the coroutine in the main event loop
                future = asyncio.run_coroutine_threadsafe(broadcast_progress(data), loop)
                # Don't wait for the result to avoid blocking
                future.add_done_callback(lambda f: None)
            else:
                # If no event loop is running, create a new one
                asyncio.run(broadcast_progress(data))
        except Exception as e:
            # Log the error but don't let it crash the watcher
            log_error(f'Failed to broadcast progress: {e}', 'SnapWatcher')
