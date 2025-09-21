from pydantic import BaseModel, validator
from typing import Optional, Dict, Any
from datetime import datetime

class SnapHookConfigDetails(BaseModel):
    """SnapHook configuration details."""
    cluster_name: str
    webhook_url: Optional[str] = None
    namespace: str = "snap"
    cert_expiry_days: int = 365
    created_at: Optional[str] = None
    last_started_at: Optional[str] = None

class SnapHookConfig(BaseModel):
    """SnapHook configuration model for serialization."""
    name: str
    snaphook_config_details: SnapHookConfigDetails
    cluster_config: Dict[str, Any]  # Store the full cluster config dict
    
    def __init__(self, name: str, snaphook_config_details: SnapHookConfigDetails, cluster_config: Dict[str, Any]):
        super().__init__(
            name=name,
            snaphook_config_details=snaphook_config_details,
            cluster_config=cluster_config
        )
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "snaphook_config_details": self.snaphook_config_details.model_dump(),
            "cluster_config": self.cluster_config
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create instance from dictionary."""
        return cls(
            name=data["name"],
            snaphook_config_details=SnapHookConfigDetails(**data["snaphook_config_details"]),
            cluster_config=data["cluster_config"]
        )

class SnapHookConfigResponse(BaseModel):
    """Response model for SnapHook configuration operations."""
    success: bool
    message: str
    snaphook_config: Optional[SnapHookConfig] = None

class SnapHookConfigListResponse(BaseModel):
    """Response model for listing SnapHook configurations."""
    success: bool
    snaphook_configs: list
    message: Optional[str] = None
