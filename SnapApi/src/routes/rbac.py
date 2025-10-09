"""
RBAC command generation routes.
Provides endpoint to generate and serve the RBAC setup command dynamically.
"""

import logging
import os
import yaml
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

logger = logging.getLogger("automation_api")
router = APIRouter()

def generate_rbac_command() -> str:
    """Generate the RBAC setup command dynamically from snapapi-rbac.yaml"""
    try:
        # Get the path to snapapi-rbac.yaml
        # Try multiple possible locations
        possible_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "snapapi-rbac.yaml"),  # src/snapapi-rbac.yaml
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "snapapi-rbac.yaml"),  # SnapApi/snapapi-rbac.yaml
            "/app/snapapi-rbac.yaml",  # Container path
            "snapapi-rbac.yaml"  # Current directory
        ]
        
        logger.info(f"Searching for snapapi-rbac.yaml in these locations: {possible_paths}")
        
        rbac_yaml_path = None
        for path in possible_paths:
            logger.info(f"Checking path: {path} - exists: {os.path.exists(path)}")
            if os.path.exists(path):
                rbac_yaml_path = path
                logger.info(f"Found snapapi-rbac.yaml at: {rbac_yaml_path}")
                break
        
        if not rbac_yaml_path:
            raise FileNotFoundError(f"snapapi-rbac.yaml not found in any of these locations: {possible_paths}")
        
        # Read the YAML file
        with open(rbac_yaml_path, 'r') as file:
            rbac_content = file.read()
        
        # Generate the one-liner command - using string concatenation to avoid f-string issues
        command = "oc new-project snap --skip-config-write 2>/dev/null || true && oc apply -f - <<EOF\n" + \
                 rbac_content + \
                 "EOF\n" + \
                 "sleep 2 && TOKEN=$(oc create token snapapi-serviceaccount -n snap --duration=8760h) && " + \
                 "API_SERVER=$(oc cluster-info | grep \"Kubernetes control plane\" | awk '{print $7}') && " + \
                 "echo \"==========================================\" && " + \
                 "echo \"SnapAPI Configuration\" && " + \
                 "echo \"==========================================\" && " + \
                 "echo \"\" && " + \
                 "echo \"Cluster API URL:\" && " + \
                 "echo \"$API_SERVER\" && " + \
                 "echo \"\" && " + \
                 "echo \"Service Account Token:\" && " + \
                 "echo \"$TOKEN\" && " + \
                 "echo \"\" && " + \
                 "echo \"==========================================\" && " + \
                 "echo \"Copy these values to your SnapUI cluster form\" && " + \
                 "echo \"==========================================\""
        
        return command
        
    except Exception as e:
        logger.error(f"Error generating RBAC command: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate RBAC command: {str(e)}")

# Global variable to store the generated RBAC command
rbac_command_cache = None

# Generate RBAC command on module import (startup)
try:
    rbac_command_cache = generate_rbac_command()
    logger.info("RBAC command generated successfully on startup")
except Exception as e:
    logger.error(f"Failed to generate RBAC command on startup: {e}")
    rbac_command_cache = None

@router.get("/rbac-command")
async def get_rbac_command():
    """
    Get the RBAC setup command.
    This command applies the RBAC configuration and returns URL and token.
    """
    try:
        global rbac_command_cache
        
        # Generate command if not cached or if we want to refresh it
        rbac_command_cache = generate_rbac_command()
        
        return {
            "success": True,
            "command": rbac_command_cache,
            "message": "RBAC command generated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error getting RBAC command: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get RBAC command: {str(e)}")

@router.post("/rbac-command/refresh")
async def refresh_rbac_command():
    """
    Refresh the RBAC command cache.
    This will regenerate the command from the current snapapi-rbac.yaml file.
    """
    try:
        global rbac_command_cache
        
        # Force regeneration
        rbac_command_cache = generate_rbac_command()
        
        return {
            "success": True,
            "command": rbac_command_cache,
            "message": "RBAC command refreshed successfully"
        }
        
    except Exception as e:
        logger.error(f"Error refreshing RBAC command: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh RBAC command: {str(e)}")
