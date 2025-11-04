from fastapi import Depends, APIRouter, HTTPException
from classes.apirequests import ClusterLoginRequest
from flows.cluster.kubectl_cluster_login import kubectl_cluster_login
from middleware.verify_token import verify_token
import logging

router = APIRouter()
logger = logging.getLogger("automation_api")

@router.post("/login")
async def kubectl_login(login_request: ClusterLoginRequest, username: str = Depends(verify_token)):
    """Login to a Kubernetes cluster using kubectl."""
    try:
        return await kubectl_cluster_login(
           login_request.cluster_config_name,
           username
        )
    except Exception as e:
        logger.error(f"Error in kubectl_login: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
