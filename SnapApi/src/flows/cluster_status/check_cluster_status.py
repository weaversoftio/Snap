import json
import os
import uuid
import time
import ssl
from datetime import datetime
from kubernetes import client
from kubernetes.client.rest import ApiException
from classes.clusterconfig import ClusterConfig, ClusterConfigDetails
import urllib3

# Suppress InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

async def check_cluster_status(cluster_name: str) -> dict:
    """Check cluster status by running checks on nodes and save results to JSON files"""
    try:
        # Load cluster config
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cluster_config_path = os.path.join(BASE_DIR, "config", "clusters", f"{cluster_name}.json")
        
        if not os.path.exists(cluster_config_path):
            return {
                "success": False,
                "message": f"Cluster config not found for {cluster_name}"
            }
        
        with open(cluster_config_path, 'r') as f:
            cluster_data = json.load(f)
            cluster_config = ClusterConfig(
                cluster_config_details=ClusterConfigDetails(
                    kube_api_url=cluster_data["cluster_config_details"]["kube_api_url"],
                    token=cluster_data["cluster_config_details"].get("token", cluster_data["cluster_config_details"].get("kube_password", ""))
                ),
                name=cluster_data["name"]
            )
        
        # Setup Kubernetes client
        kube_config = client.Configuration()
        kube_config.host = cluster_config.cluster_config_details.kube_api_url
        kube_config.api_key = {'authorization': f'Bearer {cluster_config.cluster_config_details.token}'}
        
        verify_ssl = os.getenv('KUBE_VERIFY_SSL', 'false').lower() == 'true'
        kube_config.verify_ssl = verify_ssl
        
        if not verify_ssl:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            kube_config.ssl_ca_cert = None
            kube_config.cert_file = None
            kube_config.key_file = None
        
        api_client = client.ApiClient(kube_config)
        core_api = client.CoreV1Api(api_client)
        
        # Get list of nodes
        try:
            nodes = core_api.list_node()
        except ApiException as e:
            return {
                "success": False,
                "message": f"Failed to list nodes: {str(e)}"
            }
        
        if not nodes.items:
            return {
                "success": True,
                "message": "No nodes found in cluster"
            }
        
        # Check each node by creating temporary pods
        namespace = "default"
        pod_name_prefix = f"node-checker-{uuid.uuid4().hex[:6]}"
        created_pods = []  # List of (namespace, pod_name, node_name) tuples
        
        # Ensure status directory exists
        status_dir = os.path.join(BASE_DIR, "config", "cluster_status", cluster_name)
        os.makedirs(status_dir, exist_ok=True)
        
        # Clean up any old status files before starting new check
        # This ensures we don't have stale data
        try:
            for filename in os.listdir(status_dir):
                if filename.endswith('.json'):
                    old_file = os.path.join(status_dir, filename)
                    try:
                        os.remove(old_file)
                    except Exception:
                        pass  # Ignore errors removing old files
        except Exception:
            pass  # Ignore errors listing directory
        
        try:
            # Create pods on each node
            for node in nodes.items:
                node_name = node.metadata.name
                # Create a valid pod name (Kubernetes names: lowercase, alphanumeric, hyphens)
                safe_node_name = node_name.lower().replace('_', '-')[:20]
                pod_name = f"{pod_name_prefix}-{safe_node_name}"
                
                # Script to run on the host (same as check_nodes_project)
                cmd = """
                chroot /host /bin/sh -c '
                    echo "NODE_NAME: $HOSTNAME"
                    
                    echo -n "CRIO_VERSION: "
                    if command -v crio >/dev/null 2>&1; then
                        crio --version | head -n 1
                    else
                        echo "NOT_FOUND"
                    fi
                    
                    echo -n "CRIU_INSTALLED: "
                    if command -v criu >/dev/null 2>&1; then
                        echo "YES"
                    else
                        echo "NO"
                    fi
                    
                    echo -n "RUNC_VERSION: "
                    if command -v runc >/dev/null 2>&1; then
                        runc --version | head -n 1
                    else
                        echo "NOT_FOUND"
                    fi
                '
                """
                
                container = client.V1Container(
                    name="node-checker",
                    image="registry.access.redhat.com/ubi9/ubi:latest",
                    command=["/bin/sh", "-c", cmd],
                    security_context=client.V1SecurityContext(privileged=True),
                    volume_mounts=[
                        client.V1VolumeMount(
                            mount_path="/host",
                            name="host-root"
                        )
                    ]
                )
                
                pod_spec = client.V1PodSpec(
                    host_network=True,
                    host_pid=True,
                    host_ipc=True,
                    containers=[container],
                    volumes=[
                        client.V1Volume(
                            name="host-root",
                            host_path=client.V1HostPathVolumeSource(path="/")
                        )
                    ],
                    node_name=node_name,
                    restart_policy="Never",
                    tolerations=[
                        client.V1Toleration(operator="Exists")
                    ]
                )
                
                pod = client.V1Pod(
                    api_version="v1",
                    kind="Pod",
                    metadata=client.V1ObjectMeta(
                        name=pod_name,
                        namespace=namespace
                    ),
                    spec=pod_spec
                )
                
                try:
                    created_pod = core_api.create_namespaced_pod(namespace=namespace, body=pod)
                    created_pods.append((namespace, pod_name, node_name))
                except ApiException as e:
                    # Save error status
                    status_file = os.path.join(status_dir, f"{node_name}.json")
                    error_status = {
                        "node_name": node_name,
                        "timestamp": datetime.now().isoformat(),
                        "checks": {
                            "crio": "crio:Failed to create check pod",
                            "criu": "criu:Failed to create check pod",
                            "runc": "runc:Failed to create check pod"
                        }
                    }
                    with open(status_file, 'w') as f:
                        json.dump(error_status, f, indent=2)
                    continue
            
            # Wait for pods to complete
            time.sleep(10)
            
            # Get logs from each pod and parse results
            for namespace, pod_name, node_name in created_pods:
                status_file = os.path.join(status_dir, f"{node_name}.json")
                
                try:
                    # Wait for pod to be ready
                    max_wait = 30
                    waited = 0
                    while waited < max_wait:
                        pod_status = core_api.read_namespaced_pod_status(pod_name, namespace)
                        if pod_status.status.phase in ['Succeeded', 'Failed', 'Running']:
                            break
                        time.sleep(2)
                        waited += 2
                    
                    # Get pod logs
                    log = core_api.read_namespaced_pod_log(pod_name, namespace)
                    
                    # Parse logs (same logic as check_nodes_project)
                    crio_version = "Unknown"
                    criu_installed = "Unknown"
                    runc_version = "Unknown"
                    
                    for line in log.split('\n'):
                        if "CRIO_VERSION:" in line:
                            crio_version = line.split("CRIO_VERSION:")[1].strip()
                        if "CRIU_INSTALLED:" in line:
                            criu_installed = line.split("CRIU_INSTALLED:")[1].strip()
                        if "RUNC_VERSION:" in line:
                            runc_version = line.split("RUNC_VERSION:")[1].strip()
                    
                    # Format checks (same format as report_node_status expects)
                    checks = {
                        "crio": f"crio:{crio_version}" if crio_version != "Unknown" else "crio:NOT_FOUND",
                        "criu": f"criu:{'Installed' if criu_installed == 'YES' else 'Not Installed'}",
                        "runc": f"runc:{runc_version}" if runc_version != "Unknown" else "runc:NOT_FOUND"
                    }
                    
                    # Save node status to JSON file
                    node_status = {
                        "node_name": node_name,
                        "timestamp": datetime.now().isoformat(),
                        "checks": checks
                    }
                    
                    # Ensure we overwrite any existing file
                    try:
                        if os.path.exists(status_file):
                            os.remove(status_file)
                    except Exception:
                        pass  # Ignore if file doesn't exist or can't be removed
                    
                    # Write new status file (use atomic write to ensure consistency)
                    import tempfile
                    temp_file = status_file + '.tmp'
                    try:
                        with open(temp_file, 'w') as f:
                            json.dump(node_status, f, indent=2)
                            f.flush()
                            if hasattr(f, 'fileno'):
                                os.fsync(f.fileno())
                        
                        # Atomic move to final location
                        os.replace(temp_file, status_file)
                    except Exception as e:
                        # Clean up temp file if something went wrong
                        if os.path.exists(temp_file):
                            try:
                                os.remove(temp_file)
                            except:
                                pass
                        raise e
                    
                except ApiException as e:
                    # Save error status
                    error_status = {
                        "node_name": node_name,
                        "timestamp": datetime.now().isoformat(),
                        "checks": {
                            "crio": "crio:Failed to retrieve check results",
                            "criu": "criu:Failed to retrieve check results",
                            "runc": "runc:Failed to retrieve check results"
                        }
                    }
                    with open(status_file, 'w') as f:
                        json.dump(error_status, f, indent=2)
        
        finally:
            # Clean up pods
            for namespace, pod_name, _ in created_pods:
                try:
                    core_api.delete_namespaced_pod(pod_name, namespace, grace_period_seconds=0)
                except ApiException:
                    pass  # Ignore cleanup errors
        
        return {
            "success": True,
            "message": f"Cluster status check completed for {cluster_name}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to check cluster status: {str(e)}"
        }

