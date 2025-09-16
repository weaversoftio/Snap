from pydantic import BaseModel
from typing import Optional, Dict, List, Any
from datetime import datetime

class NodeCheckResult(BaseModel):
    check_name: str
    status: str  # "pass", "fail"
    details: Optional[str] = None

class NodeStatusReport(BaseModel):
    node_name: str
    timestamp: datetime
    checks: Dict[str, str]  # check_name: "status:details"

class ClusterStatusRequest(BaseModel):
    cluster_name: str
    node_name: str
    timestamp: str
    checks: Dict[str, str]

class ClusterStatusResponse(BaseModel):
    success: bool
    message: str
    node_status: Optional[NodeStatusReport] = None

class ClusterStatusSummary(BaseModel):
    total_nodes: int
    ready_nodes: int
    not_ready_nodes: int
    overall_status: str  # "ready", "not_ready"
    node_details: List[Dict[str, Any]]

class ClusterStatusListResponse(BaseModel):
    success: bool
    cluster_status: Optional[ClusterStatusSummary] = None
    message: str
