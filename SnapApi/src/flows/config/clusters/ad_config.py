"""
AD Configuration management for clusters
"""

import os
import json
import logging
from pydantic import BaseModel
from typing import Optional, List
from services.ad_auth_service import ADAuthService

logger = logging.getLogger("automation_api")


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


async def get_ad_config(cluster_name: str) -> ADConfigResponse:
    """Get AD configuration for a cluster"""
    try:
        path = f"config/clusters/{cluster_name}.json"
        
        if not os.path.exists(path):
            return ADConfigResponse(
                success=False,
                message=f"Cluster config file {cluster_name} does not exist"
            )
        
        with open(path, "r") as f:
            cluster_data = json.load(f)
        
        cluster_details = cluster_data.get("cluster_config_details", {})
        
        ad_config = {
            "ad_enabled": cluster_details.get("ad_enabled", False),
            "ad_type": cluster_details.get("ad_type"),
            "ad_server": cluster_details.get("ad_server"),
            "ad_port": cluster_details.get("ad_port"),
            "ad_base_dn": cluster_details.get("ad_base_dn"),
            "ad_service_dn": cluster_details.get("ad_service_dn"),
            "ad_service_password": cluster_details.get("ad_service_password"),
            "ad_allowed_groups": cluster_details.get("ad_allowed_groups", []),
            "ad_use_ssl": cluster_details.get("ad_use_ssl", False)
        }
        
        return ADConfigResponse(
            success=True,
            message="AD configuration retrieved successfully",
            ad_config=ad_config
        )
    except Exception as e:
        logger.error(f"Error getting AD config for cluster {cluster_name}: {e}")
        return ADConfigResponse(
            success=False,
            message=f"Error retrieving AD configuration: {str(e)}"
        )


async def update_ad_config(cluster_name: str, request: ADConfigRequest) -> ADConfigResponse:
    """Update AD configuration for a cluster"""
    try:
        path = f"config/clusters/{cluster_name}.json"
        
        if not os.path.exists(path):
            return ADConfigResponse(
                success=False,
                message=f"Cluster config file {cluster_name} does not exist"
            )
        
        # Load existing cluster config
        with open(path, "r") as f:
            cluster_data = json.load(f)
        
        # Update AD configuration in cluster_details
        cluster_details = cluster_data.get("cluster_config_details", {})
        cluster_details["ad_enabled"] = request.ad_enabled
        cluster_details["ad_type"] = request.ad_type
        cluster_details["ad_server"] = request.ad_server
        cluster_details["ad_port"] = request.ad_port
        cluster_details["ad_base_dn"] = request.ad_base_dn
        cluster_details["ad_service_dn"] = request.ad_service_dn
        cluster_details["ad_service_password"] = request.ad_service_password
        cluster_details["ad_allowed_groups"] = request.ad_allowed_groups or []
        cluster_details["ad_use_ssl"] = request.ad_use_ssl
        
        # Save updated config
        with open(path, "w") as f:
            json.dump(cluster_data, f, indent=4)
        
        return ADConfigResponse(
            success=True,
            message=f"AD configuration updated successfully for cluster {cluster_name}",
            ad_config=cluster_details
        )
    except Exception as e:
        logger.error(f"Error updating AD config for cluster {cluster_name}: {e}")
        return ADConfigResponse(
            success=False,
            message=f"Error updating AD configuration: {str(e)}"
        )


async def test_ad_connection(cluster_name: str, request: Optional[ADTestConnectionRequest] = None) -> ADTestConnectionResponse:
    """Test AD connection"""
    try:
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
            result = ADAuthService.test_connection(cluster_name, ad_config)
        else:
            # Test with existing cluster config
            result = ADAuthService.test_connection(cluster_name)
        
        return ADTestConnectionResponse(
            success=result.get("success", False),
            message=result.get("message", "Connection test failed")
        )
    except Exception as e:
        logger.error(f"Error testing AD connection: {e}")
        return ADTestConnectionResponse(
            success=False,
            message=f"Error testing connection: {str(e)}"
        )


async def get_ad_groups(cluster_name: str) -> ADGroupsResponse:
    """Get available AD groups for a cluster"""
    try:
        result = ADAuthService.get_available_groups(cluster_name)
        
        return ADGroupsResponse(
            success=result.get("success", False),
            message=result.get("message", ""),
            groups=result.get("groups", [])
        )
    except Exception as e:
        logger.error(f"Error getting AD groups for cluster {cluster_name}: {e}")
        return ADGroupsResponse(
            success=False,
            message=f"Error retrieving groups: {str(e)}",
            groups=[]
        )

