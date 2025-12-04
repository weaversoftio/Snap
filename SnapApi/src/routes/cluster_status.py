from fastapi import APIRouter, Depends
from pydantic import BaseModel
from classes.cluster_status_models import (
    ClusterStatusRequest,
    ClusterStatusResponse,
    ClusterStatusListResponse,
    ClusterStatusSummary
)
from flows.cluster_status.report_node_status import report_node_status
from flows.cluster_status.get_cluster_status import get_cluster_status
from flows.cluster_status.check_cluster_status import check_cluster_status
from middleware.verify_token import verify_token
import json
import os
from datetime import datetime

router = APIRouter()

class RescanClusterRequest(BaseModel):
    cluster_name: str

class RescanClusterResponse(BaseModel):
    success: bool
    message: str

@router.post("/report", response_model=ClusterStatusResponse)
async def report_node_status_endpoint(request: ClusterStatusRequest):
    """Report node status from DaemonSet"""
    return await report_node_status(request)

@router.get("/summary", response_model=ClusterStatusListResponse)
async def get_cluster_status_endpoint(cluster_name: str = None):
    """Get overall cluster status summary"""
    return await get_cluster_status(cluster_name)

@router.post("/rescan", response_model=RescanClusterResponse)
async def rescan_cluster_status_endpoint(request: RescanClusterRequest, username: str = Depends(verify_token)):
    """Rescan cluster status by running checks on all nodes"""
    result = await check_cluster_status(request.cluster_name)
    return RescanClusterResponse(
        success=result.get("success", False),
        message=result.get("message", "Unknown error")
    )
