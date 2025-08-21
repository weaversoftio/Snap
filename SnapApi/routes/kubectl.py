from fastapi import Depends, APIRouter
from classes.apirequests import ClusterLoginRequest
from flows.cluster.kubectl_cluster_login import kubectl_cluster_login
from middleware.verify_token import verify_token

router = APIRouter()

@router.post("/login")
async def kubectl_login(request: ClusterLoginRequest, username: str = Depends(verify_token)):
    return await kubectl_cluster_login(
       request.cluster_config_name,
       username
    )
