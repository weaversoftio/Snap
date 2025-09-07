from pydantic import BaseModel, validator
from typing import Optional, Literal

class ClusterConfigDetails(BaseModel):
    kube_api_url: str
    kube_username: Optional[str] = None
    kube_password: str  # This field stores either password or token
    nodes_username: str
    auth_method: Literal["username_password", "token"] = "username_password"
    
    @validator('kube_username')
    def validate_username_for_auth_method(cls, v, values):
        auth_method = values.get('auth_method')
        # If auth_method is not yet processed, infer it from username presence for backward compatibility
        if auth_method is None:
            auth_method = "token" if not v else "username_password"
        
        if auth_method == 'username_password' and not v:
            raise ValueError('Username is required for username_password authentication')
        elif auth_method == 'token' and v:
            # Clear username for token auth to maintain backward compatibility
            return None
        return v
    
    @validator('kube_password')
    def validate_password_or_token(cls, v, values):
        if not v or not v.strip():
            auth_method = values.get('auth_method', 'username_password')
            field_name = 'Token' if auth_method == 'token' else 'Password'
            raise ValueError(f'{field_name} is required')
        return v

class ClusterConfig(BaseModel):
    cluster_config_details: ClusterConfigDetails
    name: str

    def __init__(self, cluster_config_details: ClusterConfigDetails, name: str):
        super().__init__(cluster_config_details=cluster_config_details, name=name)
    
    def to_dict(self):
        return {
            "cluster_config_details": self.cluster_config_details.model_dump(),
            "name": self.name
        }
