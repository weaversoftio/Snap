"""
App-level AD Configuration management
"""

import os
import json
import logging
from pydantic import BaseModel
from typing import Optional, List

logger = logging.getLogger("automation_api")

AD_CONFIG_PATH = "config/security/ad_config.json"


class ADConfigRequest(BaseModel):
    ad_enabled: bool = False
    ad_type: Optional[str] = None  # "openldap" or "real_ad"
    ad_server: Optional[str] = None
    ad_port: Optional[int] = None
    ad_base_dn: Optional[str] = None
    ad_service_dn: Optional[str] = None
    ad_service_password: Optional[str] = None
    ad_allowed_groups: Optional[List[str]] = None
    ad_use_ssl: Optional[bool] = False


class ADConfigResponse(BaseModel):
    success: bool
    message: str
    ad_config: Optional[dict] = None


class ADTestConnectionRequest(BaseModel):
    ad_type: str
    ad_server: str
    ad_port: Optional[int] = None
    ad_base_dn: str
    ad_service_dn: str
    ad_service_password: str
    ad_use_ssl: Optional[bool] = False


class ADTestConnectionResponse(BaseModel):
    success: bool
    message: str


class ADGroupsResponse(BaseModel):
    success: bool
    message: str
    groups: List[dict] = []


def get_ad_config() -> ADConfigResponse:
    """Get app-level AD configuration"""
    try:
        if not os.path.exists(AD_CONFIG_PATH):
            return ADConfigResponse(
                success=True,
                message="AD configuration not set",
                ad_config={
                    "ad_enabled": False,
                    "ad_type": None,
                    "ad_server": None,
                    "ad_port": None,
                    "ad_base_dn": None,
                    "ad_service_dn": None,
                    "ad_service_password": None,
                    "ad_allowed_groups": [],
                    "ad_use_ssl": False
                }
            )
        
        with open(AD_CONFIG_PATH, "r") as f:
            ad_config = json.load(f)
        
        return ADConfigResponse(
            success=True,
            message="AD configuration retrieved successfully",
            ad_config=ad_config
        )
    except Exception as e:
        logger.error(f"Error getting AD config: {e}")
        return ADConfigResponse(
            success=False,
            message=f"Error retrieving AD configuration: {str(e)}"
        )


def update_ad_config(request: ADConfigRequest) -> ADConfigResponse:
    """Update app-level AD configuration"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(AD_CONFIG_PATH), exist_ok=True)
        
        ad_config = {
            "ad_enabled": request.ad_enabled,
            "ad_type": request.ad_type,
            "ad_server": request.ad_server,
            "ad_port": request.ad_port,
            "ad_base_dn": request.ad_base_dn,
            "ad_service_dn": request.ad_service_dn,
            "ad_service_password": request.ad_service_password,
            "ad_allowed_groups": request.ad_allowed_groups or [],
            "ad_use_ssl": request.ad_use_ssl
        }
        
        # Save config
        with open(AD_CONFIG_PATH, "w") as f:
            json.dump(ad_config, f, indent=4)
        
        return ADConfigResponse(
            success=True,
            message="AD configuration updated successfully",
            ad_config=ad_config
        )
    except Exception as e:
        logger.error(f"Error updating AD config: {e}")
        return ADConfigResponse(
            success=False,
            message=f"Error updating AD configuration: {str(e)}"
        )


async def test_ad_connection(request: Optional[ADTestConnectionRequest] = None) -> ADTestConnectionResponse:
    """Test AD connection"""
    try:
        from services.ad_auth_service import ADAuthService
        
        if request:
            # Test with provided config
            ad_config = {
                "ad_type": request.ad_type,
                "ad_server": request.ad_server,
                "ad_port": request.ad_port or (636 if request.ad_use_ssl else 389),
                "ad_base_dn": request.ad_base_dn,
                "ad_service_dn": request.ad_service_dn,
                "ad_service_password": request.ad_service_password,
                "ad_use_ssl": request.ad_use_ssl
            }
            result = ADAuthService.test_connection(ad_config)
        else:
            # Test with existing app config
            config_result = get_ad_config()
            if not config_result.success or not config_result.ad_config.get("ad_enabled"):
                return ADTestConnectionResponse(
                    success=False,
                    message="AD not enabled or configured"
                )
            result = ADAuthService.test_connection(config_result.ad_config)
        
        return ADTestConnectionResponse(
            success=result.get("success", False),
            message=result.get("message", "Connection test failed")
        )
    except Exception as e:
        logger.error(f"Error testing AD connection: {e}")
        import traceback
        logger.error(traceback.format_exc())
        error_message = str(e) if e else "Unknown error occurred"
        return ADTestConnectionResponse(
            success=False,
            message=f"Error testing connection: {error_message}"
        )


async def get_ad_groups() -> ADGroupsResponse:
    """Get available AD groups from app-level config"""
    try:
        from services.ad_auth_service import ADAuthService
        result = ADAuthService.get_available_groups()
        
        return ADGroupsResponse(
            success=result.get("success", False),
            message=result.get("message", ""),
            groups=result.get("groups", [])
        )
    except Exception as e:
        logger.error(f"Error getting AD groups: {e}")
        return ADGroupsResponse(
            success=False,
            message=f"Error retrieving groups: {str(e)}",
            groups=[]
        )

