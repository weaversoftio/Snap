from fastapi import APIRouter
from classes.cluster_cache_models import (
    ClusterCacheRequest, 
    ClusterCacheResponse, 
    ClusterCacheListResponse
)
from flows.config.clusterCache.create_cluster_cache import create_cluster_cache
from flows.config.clusterCache.update_cluster_cache import update_cluster_cache
from flows.config.clusterCache.list_cluster_cache import list_cluster_cache
from flows.config.clusterCache.delete_cluster_cache import delete_cluster_cache, DeleteClusterCacheRequest
from flows.config.clusterCache.get_cluster_cache import get_cluster_cache

router = APIRouter()

@router.post("/create", response_model=ClusterCacheResponse)
async def create_cluster_cache_endpoint(request: ClusterCacheRequest):
    """Create a new cluster cache configuration"""
    return await create_cluster_cache(request)

@router.put("/update", response_model=ClusterCacheResponse)
async def update_cluster_cache_endpoint(request: ClusterCacheRequest):
    """Update an existing cluster cache configuration"""
    return await update_cluster_cache(request)

@router.get("/list", response_model=ClusterCacheListResponse)
async def list_cluster_cache_endpoint():
    """List all cluster cache configurations"""
    return await list_cluster_cache()

@router.get("/get/{cluster_name}", response_model=ClusterCacheResponse)
async def get_cluster_cache_endpoint(cluster_name: str):
    """Get cluster cache configuration for a specific cluster"""
    return await get_cluster_cache(cluster_name)

@router.delete("/delete", response_model=ClusterCacheResponse)
async def delete_cluster_cache_endpoint(request: DeleteClusterCacheRequest):
    """Delete a cluster cache configuration"""
    return await delete_cluster_cache(request)
