import json
import os
from datetime import datetime, timedelta
from classes.cluster_status_models import ClusterStatusListResponse, ClusterStatusSummary

async def get_cluster_status(cluster_name: str = None) -> ClusterStatusListResponse:
    """Get overall cluster status summary"""
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
                message="No cluster status data available"
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
                    last_update = datetime.fromisoformat(node_data['timestamp'].replace('Z', '+00:00'))
                    is_recent = datetime.now(last_update.tzinfo) - last_update < timedelta(minutes=10)
                    
                    # Check if all required checks pass
                    checks = node_data.get('checks', {})
                    crio_ok = checks.get('crio', '').startswith('crio:pass')
                    criu_ok = checks.get('criu', '').startswith('criu:pass')
                    criu_config_ok = checks.get('criu_config', '').startswith('criu_config:pass')
                    
                    node_ready = crio_ok and criu_ok and criu_config_ok and is_recent
                    
                    if node_ready:
                        ready_nodes += 1
                    else:
                        not_ready_nodes += 1
                    
                    # Prepare node details
                    node_detail = {
                        'node_name': node_name,
                        'ready': node_ready,
                        'last_update': node_data['timestamp'],
                        'is_recent': is_recent,
                        'checks': {
                            'crio': {
                                'status': 'pass' if crio_ok else 'fail',
                                'details': checks.get('crio', '')
                            },
                            'criu': {
                                'status': 'pass' if criu_ok else 'fail',
                                'details': checks.get('criu', '')
                            },
                            'criu_config': {
                                'status': 'pass' if criu_config_ok else 'fail',
                                'details': checks.get('criu_config', '')
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
