import json
import os
from datetime import datetime, timedelta
from classes.cluster_status_models import ClusterStatusListResponse, ClusterStatusSummary

# Get version requirements from environment variables with defaults
# These can be overridden via environment variables in docker-compose.yml or .env file
# Example: CRIO_VERSION_REQUIRED=1.31.2 RUNC_VERSION_REQUIRED=1.2.4
CRIO_VERSION_REQUIRED = os.getenv('CRIO_VERSION_REQUIRED', '1.31.2')
RUNC_VERSION_REQUIRED = os.getenv('RUNC_VERSION_REQUIRED', '1.2.4')

async def get_cluster_status(cluster_name: str = None) -> ClusterStatusListResponse:
    """Get overall cluster status summary from saved JSON files"""
    try:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        if cluster_name:
            status_dir = os.path.join(BASE_DIR, "config", "cluster_status", cluster_name)
        else:
            status_dir = os.path.join(BASE_DIR, "config", "cluster_status")
        
        if not os.path.exists(status_dir):
            return ClusterStatusListResponse(
                success=True,
                cluster_status=ClusterStatusSummary(
                    total_nodes=0,
                    ready_nodes=0,
                    not_ready_nodes=0,
                    overall_status="not_ready",
                    node_details=[]
                ),
                message="No cluster status data available. Run cluster check first."
            )
        
        # Read all node status files
        node_details = []
        ready_nodes = 0
        not_ready_nodes = 0
        
        for filename in os.listdir(status_dir):
            if filename.endswith('.json'):
                node_name = filename[:-5]  # Remove .json extension
                status_file = os.path.join(status_dir, filename)
                
                try:
                    with open(status_file, 'r') as f:
                        node_data = json.load(f)
                    
                    # Check if status is recent (within last 10 minutes)
                    timestamp_str = node_data.get('timestamp', '')
                    if timestamp_str:
                        last_update = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        is_recent = datetime.now(last_update.tzinfo) - last_update < timedelta(minutes=10)
                    else:
                        is_recent = False
                    
                    # Check if all required checks pass (same validation as check_nodes_project)
                    checks = node_data.get('checks', {})
                    crio_check = checks.get('crio', '')
                    criu_check = checks.get('criu', '')
                    runc_check = checks.get('runc', '')
                    
                    # Validate using environment variable requirements
                    # crio should contain the required version
                    # criu should be "Installed" (new format) or check for CRIU being installed (old format had "Version:")
                    # runc should contain the required version
                    crio_ok = CRIO_VERSION_REQUIRED in crio_check
                    # Handle both new format ("criu:Installed") and old format ("criu:Version: X.X")
                    # For CRIU, we just need it to be installed, so check if it's NOT "Not Installed"
                    criu_ok = "Installed" in criu_check and "Not Installed" not in criu_check
                    runc_ok = RUNC_VERSION_REQUIRED in runc_check
                    
                    node_ready = crio_ok and criu_ok and runc_ok and is_recent
                    
                    if node_ready:
                        ready_nodes += 1
                    else:
                        not_ready_nodes += 1
                    
                    # Prepare node details
                    node_detail = {
                        'node_name': node_name,
                        'ready': node_ready,
                        'last_update': timestamp_str,
                        'is_recent': is_recent,
                        'checks': {
                            'crio': {
                                'status': 'pass' if crio_ok else 'fail',
                                'details': crio_check
                            },
                            'criu': {
                                'status': 'pass' if criu_ok else 'fail',
                                'details': criu_check
                            },
                            'runc': {
                                'status': 'pass' if runc_ok else 'fail',
                                'details': runc_check
                            }
                        }
                    }
                    
                    node_details.append(node_detail)
                    
                except Exception as e:
                    # Handle corrupted or invalid status files
                    not_ready_nodes += 1
                    node_details.append({
                        'node_name': node_name,
                        'ready': False,
                        'last_update': None,
                        'is_recent': False,
                        'error': f"Failed to parse status: {str(e)}"
                    })
        
        total_nodes = len(node_details)
        overall_status = "ready" if ready_nodes == total_nodes and total_nodes > 0 else "not_ready"
        
        cluster_status = ClusterStatusSummary(
            total_nodes=total_nodes,
            ready_nodes=ready_nodes,
            not_ready_nodes=not_ready_nodes,
            overall_status=overall_status,
            node_details=node_details
        )
        
        return ClusterStatusListResponse(
            success=True,
            cluster_status=cluster_status,
            message=f"Cluster status: {ready_nodes}/{total_nodes} nodes ready"
        )
        
    except Exception as e:
        return ClusterStatusListResponse(
            success=False,
            message=f"Failed to get cluster status: {str(e)}"
        )
