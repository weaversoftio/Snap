from fastapi import APIRouter, Depends
from classes.apirequests import ClusterLoginRequest
from flows.cluster.enable_checkpoint import enable_checkpointing, ClusterRequest
from flows.cluster.install_runc import install_runc, RunCRequest
from flows.cluster.verify_checkpointing import verify_checkpointing, CheckClusterResponse, VerifyCheckpointRequest
from flows.cluster.get_statistics import get_statistics
from middleware.verify_token import verify_token

router = APIRouter()

@router.post("/enable_checkpointing")
async def enable_checkpointing_endpoint(request: ClusterRequest, username: str = Depends(verify_token)):
    # DEPRECATED: This endpoint is no longer used after deploying the DaemonSet
    # The DaemonSet automatically handles checkpointing enablement
    return {"success": False, "message": "This endpoint is deprecated. Checkpointing is now handled automatically by the DaemonSet."}

@router.post("/install_runc")
async def install_runc_endpoint(request: RunCRequest, username: str = Depends(verify_token)):
    # DEPRECATED: This endpoint is no longer used after deploying the DaemonSet
    # The DaemonSet automatically handles runc installation
    return {"success": False, "message": "This endpoint is deprecated. runc installation is now handled automatically by the DaemonSet."}

@router.post("/verify_checkpointing", response_model=CheckClusterResponse)
async def verify_checkpointing_endpoint(request: VerifyCheckpointRequest, username: str = Depends(verify_token)):
    # DEPRECATED: This endpoint is no longer used after deploying the DaemonSet
    # The DaemonSet automatically monitors cluster health and reports status to UI
    return {"success": False, "message": "This endpoint is deprecated. Cluster verification is now handled automatically by the DaemonSet."}

@router.get("/statistics")
async def statistics_endpoint():
    return await get_statistics()