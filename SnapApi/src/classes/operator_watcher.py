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
        # Thread-safe tracking to prevent duplicate checkpoint attempts
        self._processing_pods = set()  # Track pods currently being checkpointed
        self._checkpointed_pods = set()  # Track pods that have been successfully checkpointed
        self._tracking_lock = threading.Lock()  # Lock for thread-safe set operations
        
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
                logger.info(f'[SnapWatcher] SSL verification disabled for cluster {self.cluster_name}')
            else:
                logger.info(f'[SnapWatcher] SSL verification enabled for cluster {self.cluster_name}')
            
            # Create API client with the configuration
            self.kube_client = client.ApiClient(kube_config)
            logger.info(f'[SnapWatcher] Configured Kubernetes client for cluster {self.cluster_name}')
            
        except Exception as e:
            logger.error(f'[SnapWatcher] Could not setup Kubernetes configuration: {e}')
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
                logger.error(f'[SnapWatcher] Kubernetes client not ready, cannot start watcher')
                return False
            
            if self.is_running:
                logger.warning(f'[SnapWatcher] Watcher is already running')
                return True
            
            logger.info(f'[SnapWatcher] Starting SnapWatcher for cluster {self.cluster_name}')
            
            # Reset stop event
            self._stop_event.clear()
            
            # Start watch thread
            self.watch_thread = threading.Thread(target=self._watch_pods, daemon=True)
            self.watch_thread.start()
            
            self.is_running = True
            logger.info(f'[SnapWatcher] SnapWatcher started successfully for cluster {self.cluster_name}')
            return True
            
        except Exception as e:
            logger.error(f'[SnapWatcher] Failed to start SnapWatcher: {e}')
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
                logger.warning(f'[SnapWatcher] Watcher is not running')
                return True
            
            logger.info(f'[SnapWatcher] Stopping SnapWatcher for cluster {self.cluster_name}')
            
            # Signal stop event
            self._stop_event.set()
            
            # Wait for watch thread to finish
            if self.watch_thread and self.watch_thread.is_alive():
                self.watch_thread.join(timeout=10)  # Wait up to 10 seconds
            
            self.is_running = False
            self.watch_thread = None
            
            logger.info(f'[SnapWatcher] SnapWatcher stopped successfully for cluster {self.cluster_name}')
            return True
            
        except Exception as e:
            logger.error(f'[SnapWatcher] Failed to stop SnapWatcher: {e}')
            return False
    
    def _watch_pods(self) -> None:
        """
        Watch for pod events using Kubernetes watch API.
        This method runs in a separate thread and automatically restarts on timeout/errors.
        """
        # Create a new event loop for this thread
        # This is necessary because asyncio.run() cannot be called if there's already an event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            while not self._stop_event.is_set():
                try:
                    v1 = client.CoreV1Api(self.kube_client)
                    w = watch.Watch()
                    
                    # Configure label selector to filter at Kubernetes API level
                    # Include pods with snap=true but exclude pods with mutated=true
                    label_selector = "snap.weaversoft.io/snap=true,!snap.weaversoft.io/mutated"
                    
                    # First, list existing pods that match the criteria and process them
                    # This handles pods that already exist when the watcher starts
                    logger.info(f'[SnapWatcher] Checking for existing pods with label selector: {label_selector}')
                    try:
                        if self.scope == "namespace":
                            existing_pods = v1.list_namespaced_pod(namespace=self.namespace, label_selector=label_selector)
                        else:
                            existing_pods = v1.list_pod_for_all_namespaces(label_selector=label_selector)
                        
                        if existing_pods.items:
                            logger.info(f'[SnapWatcher] Found {len(existing_pods.items)} existing pod(s) matching criteria, processing them')
                            for pod in existing_pods.items:
                                if self._stop_event.is_set():
                                    break
                                # Create an ADDED event for each existing pod
                                pod_name = getattr(pod.metadata, 'name', 'unknown') if pod.metadata else 'unknown'
                                pod_namespace = getattr(pod.metadata, 'namespace', 'unknown') if pod.metadata else 'unknown'
                                logger.info(f'[SnapWatcher] Processing existing pod: {pod_namespace}/{pod_name}')
                                event = {'type': 'ADDED', 'object': pod}
                                try:
                                    loop.run_until_complete(self._process_pod_event(event))
                                except Exception as e:
                                    logger.error(f'[SnapWatcher] Error processing existing pod {pod_name}: {e}')
                                    import traceback
                                    logger.error(f'[SnapWatcher] Traceback: {traceback.format_exc()}')
                        else:
                            logger.info(f'[SnapWatcher] No existing pods found matching criteria')
                    except Exception as e:
                        logger.warning(f'[SnapWatcher] Error listing existing pods (will continue with watch): {e}')
                    
                    # Now start watching for future changes
                    # Configure watch parameters based on scope with label filtering
                    if self.scope == "namespace":
                        logger.info(f'[SnapWatcher] Starting watch for pods in namespace: {self.namespace} with label selector: {label_selector}')
                        stream = w.stream(v1.list_namespaced_pod, namespace=self.namespace, label_selector=label_selector, timeout_seconds=0)
                    else:
                        logger.info(f'[SnapWatcher] Starting watch for pods cluster-wide with label selector: {label_selector}')
                        stream = w.stream(v1.list_pod_for_all_namespaces, label_selector=label_selector, timeout_seconds=0)
                    
                    logger.info(f'[SnapWatcher] Watch stream established for cluster {self.cluster_name}')
                    
                    for event in stream:
                        # Check if we should stop
                        if self._stop_event.is_set():
                            logger.info(f'[SnapWatcher] Stop event received, exiting watch loop')
                            break
                        
                        
                        # Process the event
                        try:
                            # Run the async function using the thread's event loop
                            loop.run_until_complete(self._process_pod_event(event))
                        except Exception as e:
                            logger.error(f'[SnapWatcher] Error processing pod event in watch loop: {e}')
                            import traceback
                            logger.error(f'[SnapWatcher] Traceback: {traceback.format_exc()}')
                    
                    # Watch stream ended (timeout or connection closed)
                    # If we're not stopping, restart the watch loop
                    if not self._stop_event.is_set():
                        logger.warning(f'[SnapWatcher] Watch stream ended for cluster {self.cluster_name}, restarting watch loop')
                        # Small delay before restarting to avoid tight loop
                        time.sleep(1)
                    
                except Exception as e:
                    if not self._stop_event.is_set():  # Only log if not stopping
                        logger.error(f'[SnapWatcher] Error in watch loop: {e}')
                        import traceback
                        logger.error(f'[SnapWatcher] Traceback: {traceback.format_exc()}')
                        # Small delay before retrying to avoid tight loop
                        time.sleep(5)
                    else:
                        # We're stopping, break out of the loop
                        break
            
        finally:
            # Clean up the event loop when thread exits
            try:
                # Cancel any pending tasks
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                # Wait for tasks to complete cancellation
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception as e:
                logger.debug(f'[SnapWatcher] Error cleaning up event loop tasks: {e}')
            finally:
                loop.close()
            
            # Thread is exiting - update is_running flag
            self.is_running = False
            logger.info(f'[SnapWatcher] Watch thread exiting for cluster {self.cluster_name}')
    
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
            logger.error(f'[SnapWatcher] Error processing pod event: {e}')
    
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
                logger.warning(f'[SnapWatcher] Kubernetes client not ready, cannot delete pod {pod_name}')
                return False
                
            # Create CoreV1Api instance for pod operations
            v1 = client.CoreV1Api(self.kube_client)
            
            # Delete the pod
            v1.delete_namespaced_pod(
                name=pod_name,
                namespace=namespace,
                body=client.V1DeleteOptions()
            )
            
            logger.info(f'[SnapWatcher] Successfully initiated deletion of pod {pod_name} in namespace {namespace}')
            return True
            
        except client.exceptions.ApiException as e:
            logger.error(f'[SnapWatcher] Failed to delete pod {pod_name}: {e}')
            return False
        except Exception as e:
            logger.error(f'[SnapWatcher] Unexpected error deleting pod {pod_name}: {e}')
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
            logger.warning(f'[SnapWatcher] Operator not ready, skipping pod event')
            return
            
        evt_type = (event or {}).get("type") or "UNKNOWN"
        metadata = body.get("metadata", {}) or {}
        status = body.get("status", {}) or {}
        spec = body.get("spec", {}) or {}

        ns = metadata.get("namespace", "-")
        pod = metadata.get("name", "-")
        pod_key = f"{ns}/{pod}"  # Create unique key for pod tracking
        node_name = spec.get("node_name", "-")  # Use node_name instead of nodeName
        labels = metadata.get("labels", {}) or {}
        containers = spec.get("containers", []) or []

        # --- ignore deletions & terminating pods ---
        if evt_type == "DELETED" or metadata.get("deletionTimestamp"):
            # Clean up tracking when pod is deleted
            logger.debug(f'[SnapWatcher] Pod {pod} is deleted or terminating, cleaning up tracking')
            with self._tracking_lock:
                self._processing_pods.discard(pod_key)
                self._checkpointed_pods.discard(pod_key)
            return

        # Check if pod is already being processed or has been checkpointed
        with self._tracking_lock:
            if pod_key in self._processing_pods:
                logger.info(f'[SnapWatcher] Pod {pod} is already being checkpointed, skipping duplicate event')
                return
            
            if pod_key in self._checkpointed_pods:
                logger.info(f'[SnapWatcher] Pod {pod} has already been checkpointed, skipping')
                return

        # Must be Running
        pod_phase = status.get("phase")
        if pod_phase != "Running":
            return
        
        # Additional check: verify at least one container is currently running
        # A container status can have multiple state keys (running, waiting, terminated)
        # but only one represents the CURRENT state. We need to check if the container
        # is currently running, not if it has historical terminated states.
        container_statuses = status.get("container_statuses", []) or []
        has_running_container = False
        for cs in container_statuses:
            state = cs.get("state", {}) or {}
            # Check if this container is currently running
            if "running" in state:
                has_running_container = True
                break
        
        if not has_running_container:
            # Log why we're skipping - check what state the containers are in
            container_states = []
            for cs in container_statuses:
                state = cs.get("state", {}) or {}
                if "running" in state:
                    container_states.append("running")
                elif "waiting" in state:
                    container_states.append("waiting")
                elif "terminated" in state:
                    container_states.append("terminated")
                else:
                    container_states.append("unknown")
            logger.info(f'[SnapWatcher] Pod {pod} has no running containers (states: {container_states}), skipping checkpoint')
            return

        # --- Check startup probe filter (when startup probe is selected) ---
        if self.trigger == "startupProbe":
            # For startup probe trigger, we wait for pods to be ready (startup probe passed)
            # This means we only checkpoint pods that have successfully completed their startup probe
            # Must report Ready=True
            conds = status.get("conditions", []) or []
            is_ready = any(c.get("type") == "Ready" and c.get("status") == "True" for c in conds)
            if not is_ready:
                logger.info(f'[SnapWatcher] Pod {pod} is not Ready (startupProbe trigger), skipping')
                return

        # At least one container started & running
        started = False
        # Note: container_statuses was already retrieved above, but we need to check again
        # since we're checking for terminated/waiting states
        for cs in container_statuses:
            state = cs.get("state", {}) or {}
            started_flag = cs.get("started", False)

            # Check if container is running and started
            # The 'started' field might not always be present, so we also check if the container is actually running
            if "running" in state and (started_flag or state.get("running")):
                started = True
                break
        
        if not started:
            logger.info(f'[SnapWatcher] Pod {pod} has no started containers, skipping checkpoint')
            return

        # Extract container name (first container)
        container_name = "-"
        containers = spec.get("containers") or []
        if containers:
            container_name = containers[0].get("name", "-")

        # Log that this pod meets all criteria for checkpointing
        logger.info(f'[SnapWatcher] Pod {pod} meets all criteria for checkpointing - Event: {evt_type}, Namespace: {ns}, Container: {container_name}, Node: {node_name}, Scope: {self.scope}')

        # Use broadcast for snapWatcher logs - all users will see them
        
        logger.info(f'[SnapWatcher] Processing checkpoint request - Event: {evt_type}, Namespace: {ns}, Pod: {pod}, Container: {container_name}, Node: {node_name}, Scope: {self.scope}')

        # -----------------------------------------------------------------
        # Directly call the checkpoint function instead of HTTP request
        # -----------------------------------------------------------------
        # Mark pod as being processed before starting checkpoint
        with self._tracking_lock:
            self._processing_pods.add(pod_key)
        
        try:
            self._safe_broadcast_progress({
                "progress": 10, 
                "task_name": "SnapWatcher Checkpoint", 
                "message": f"Starting checkpoint for pod {pod} in namespace {ns}"
            })
            
            # Prepare the complete pod specification for the request
            pod_spec_request = PodSpecCheckpointRequest(pod_spec=body)
            
            logger.info(f'[SnapWatcher] Calling checkpoint function directly for pod {pod} in cluster {self.cluster_name}')
            
            # Call the checkpoint function directly
            result = await checkpoint_and_push_from_pod_spec(pod_spec_request, self.cluster_name, "snapwatcher-operator")
            
            logger.info(f'[SnapWatcher] Checkpoint operation completed: {result.get("success", False)}')
            
            if result.get("success"):
                logger.info(f'[SnapWatcher] Checkpoint and push completed successfully for pod {pod}')
                logger.info(f'[SnapWatcher] Image tag: {result.get("image_tag", "N/A")}')
                
                # Mark as successfully checkpointed and remove from processing
                with self._tracking_lock:
                    self._checkpointed_pods.add(pod_key)
                    self._processing_pods.discard(pod_key)
                
                # Automatically delete the pod after successful checkpoint if enabled
                if self.auto_delete_pod:
                    await broadcast_progress({
                        "progress": 95, 
                        "task_name": "SnapWatcher Checkpoint", 
                        "message": f"Deleting pod {pod} after successful checkpoint"
                    })
                    logger.info(f'[SnapWatcher] Auto-deleting pod {pod} after successful checkpoint')
                    delete_success = self.delete_pod(pod, ns)
                    if delete_success:
                        self._safe_broadcast_progress({
                            "progress": 100, 
                            "task_name": "SnapWatcher Checkpoint", 
                            "message": f"Pod {pod} deleted successfully after checkpoint"
                        })
                        logger.info(f'[SnapWatcher] Pod {pod} deletion initiated successfully')
                    else:
                        self._safe_broadcast_progress({
                            "progress": "failed", 
                            "task_name": "SnapWatcher Checkpoint", 
                            "message": f"Failed to delete pod {pod} after checkpoint"
                        })
                        logger.error(f'[SnapWatcher] Failed to delete pod {pod}')
                else:
                    self._safe_broadcast_progress({
                        "progress": 100, 
                        "task_name": "SnapWatcher Checkpoint", 
                        "message": f"Checkpoint completed successfully for pod {pod} (auto-deletion disabled)"
                    })
                    logger.info(f'[SnapWatcher] Auto-deletion disabled, keeping pod {pod}')
            else:
                # Remove from processing on failure
                with self._tracking_lock:
                    self._processing_pods.discard(pod_key)
                
                error_msg = result.get('message', 'Unknown error')
                self._safe_broadcast_progress({
                    "progress": "failed", 
                    "task_name": "SnapWatcher Checkpoint", 
                    "message": f"Checkpoint failed for pod {pod}: {error_msg}"
                })
                logger.error(f'[SnapWatcher] Checkpoint operation failed: {error_msg}')
                
        except Exception as e:
            # Remove from processing on exception
            with self._tracking_lock:
                self._processing_pods.discard(pod_key)
            
            error_msg = f"Unexpected error during checkpoint operation: {str(e)}"
            self._safe_broadcast_progress({
                "progress": "failed", 
                "task_name": "SnapWatcher Checkpoint", 
                "message": f"Checkpoint failed for pod {pod}: {error_msg}"
            })
            logger.error(f'[SnapWatcher] {error_msg}')


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
            logger.error(f'[SnapWatcher] Failed to broadcast progress: {e}')
