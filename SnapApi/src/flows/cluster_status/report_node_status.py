import json
import os
from datetime import datetime
from classes.cluster_status_models import ClusterStatusRequest, ClusterStatusResponse, NodeStatusReport

async def report_node_status(request: ClusterStatusRequest) -> ClusterStatusResponse:
    """Report node status from DaemonSet"""
    try:
        # Parse timestamp
        timestamp = datetime.fromisoformat(request.timestamp.replace('Z', '+00:00'))
        
        # Create node status report
        node_status = NodeStatusReport(
            node_name=request.node_name,
            timestamp=timestamp,
            checks=request.checks
        )
        
        # Store the status report
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        status_file = os.path.join(BASE_DIR, "config", "cluster_status", request.cluster_name, f"{request.node_name}.json")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(status_file), exist_ok=True)
        
        # Save node status
        with open(status_file, 'w') as f:
            json.dump(node_status.dict(), f, default=str, indent=2)
        
        return ClusterStatusResponse(
            success=True,
            message=f"Status reported for node {request.node_name}",
            node_status=node_status
        )
        
    except Exception as e:
        return ClusterStatusResponse(
            success=False,
            message=f"Failed to report node status: {str(e)}"
        )
