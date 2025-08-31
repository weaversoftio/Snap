# Define the request class
from pydantic import BaseModel
from typing import List, Optional

class PodCheckpointRequest(BaseModel):
    pod_name: str
    namespace: str
    node_name: str
    container_name: str
    kube_api_address: str

class PodCheckpointResponse(BaseModel):
    success: bool
    message: str
    pod_id: Optional[str] = None
    container_ids: Optional[str] = None
    checkpoint_details: Optional[str] = None
    checkpoint_path: Optional[str] = None
    pod_name: Optional[str] = None

class RegistryLoginRequest(BaseModel):
    registry_config_name: str

class PushCheckpointContainerRequest(BaseModel):
    pod_name: str
    checkpoint_name: str
    username: str
    checkpoint_config_name: str

class AutomationRequest(BaseModel):
    registry: str
    username: str
    password: str
    pod_name: str
    namespace: str
    node_name: str
    container_name: str

class ClusterLoginRequest(BaseModel):
    cluster_config_name: str
    
class CheckpointctlRequest(BaseModel):
    pod_name: str
    checkpoint_name: str

class PodCheckpointAndPushRequest(BaseModel):
    namespace: str
    kube_api_address: str
    cluster: str
    app: str
    origImageShortDigest: str
    PodTemplateHash: str

class PodSpecCheckpointRequest(BaseModel):
    pod_spec: dict
