from fastapi import APIRouter, Depends
from classes.cluster_status_models import (
    ClusterStatusRequest,
    ClusterStatusResponse,
    ClusterStatusListResponse,
    ClusterStatusSummary
)
from flows.cluster_status.report_node_status import report_node_status
from flows.cluster_status.get_cluster_status import get_cluster_status
from middleware.verify_token import verify_token
import json
import os
from datetime import datetime

router = APIRouter()

@router.post("/report", response_model=ClusterStatusResponse)
async def report_node_status_endpoint(request: ClusterStatusRequest):
    """Report node status from DaemonSet"""
    return await report_node_status(request)

@router.get("/summary", response_model=ClusterStatusListResponse)
async def get_cluster_status_endpoint(cluster_name: str = None):
    """Get overall cluster status summary"""
    return await get_cluster_status(cluster_name)
