from pydantic import BaseModel
from typing import Optional

class ClusterCacheDetails(BaseModel):
    cluster: str
    registry: str
    repo: str

class ClusterCacheRequest(BaseModel):
    cluster: str  # Points to cluster from cluster folder
    registry: str  # Points to registry from registry folder
    repo: str  # Repository name for snap images

class ClusterCacheResponse(BaseModel):
    success: bool
    message: str
    cluster_cache_details: Optional[ClusterCacheDetails] = None

class ClusterCacheListResponse(BaseModel):
    success: bool
    cluster_caches: list
    message: str

class ClusterCache(BaseModel):
    cluster_cache_details: ClusterCacheDetails
    
    def to_dict(self):
        return {
            "cluster_cache_details": {
                "cluster": self.cluster_cache_details.cluster,
                "registry": self.cluster_cache_details.registry,
                "repo": self.cluster_cache_details.repo
            }
        }
