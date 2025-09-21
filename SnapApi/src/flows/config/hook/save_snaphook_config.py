import os
import json
from datetime import datetime
from classes.snaphook_config_models import SnapHookConfig, SnapHookConfigDetails, SnapHookConfigResponse

async def save_snaphook_config(name: str, cluster_name: str, cluster_config: dict, 
                              webhook_url: str = None, namespace: str = "snap", 
                              cert_expiry_days: int = 365):
    """Save SnapHook configuration to file."""
    
    # Create config directory structure: config/hooks/<cluster_name>/
    config_dir = f"config/hooks/{cluster_name}"
    os.makedirs(config_dir, exist_ok=True)
    
    # Create config file path
    config_path = f"{config_dir}/{name}.json"
    
    try:
        # Check if config already exists
        if os.path.exists(config_path):
            return SnapHookConfigResponse(
                success=False,
                message=f"SnapHook config '{name}' already exists"
            )
        
        # Create configuration details
        config_details = SnapHookConfigDetails(
            cluster_name=cluster_name,
            webhook_url=webhook_url,
            namespace=namespace,
            cert_expiry_days=cert_expiry_days,
            created_at=datetime.now().isoformat(),
            last_started_at=None
        )
        
        # Create full configuration
        snaphook_config = SnapHookConfig(
            name=name,
            snaphook_config_details=config_details,
            cluster_config=cluster_config
        )
        
        # Save to file
        with open(config_path, "w") as f:
            json.dump(snaphook_config.to_dict(), f, indent=4)
        
        return SnapHookConfigResponse(
            success=True,
            message=f"SnapHook config '{name}' saved successfully",
            snaphook_config=snaphook_config
        )
        
    except Exception as e:
        return SnapHookConfigResponse(
            success=False,
            message=f"Error saving SnapHook config '{name}': {str(e)}"
        )

async def load_snaphook_config(name: str, cluster_name: str):
    """Load SnapHook configuration from file."""
    
    config_path = f"config/hooks/{cluster_name}/{name}.json"
    
    try:
        if not os.path.exists(config_path):
            return SnapHookConfigResponse(
                success=False,
                message=f"SnapHook config '{name}' not found"
            )
        
        with open(config_path, "r") as f:
            config_data = json.load(f)
        
        snaphook_config = SnapHookConfig.from_dict(config_data)
        
        return SnapHookConfigResponse(
            success=True,
            message=f"SnapHook config '{name}' loaded successfully",
            snaphook_config=snaphook_config
        )
        
    except Exception as e:
        return SnapHookConfigResponse(
            success=False,
            message=f"Error loading SnapHook config '{name}': {str(e)}"
        )

async def list_snaphook_configs():
    """List all SnapHook configurations."""
    
    config_dir = "config/hooks"
    
    try:
        if not os.path.exists(config_dir):
            return {
                "success": True,
                "snaphook_configs": [],
                "message": "No SnapHook configs found"
            }
        
        snaphook_configs = []
        
        # Get all cluster directories
        for cluster_name in os.listdir(config_dir):
            cluster_dir = os.path.join(config_dir, cluster_name)
            if os.path.isdir(cluster_dir):
                # Get all JSON files in the cluster directory
                for filename in os.listdir(cluster_dir):
                    if filename.endswith('.json'):
                        config_name = filename[:-5]  # Remove .json extension
                        config_response = await load_snaphook_config(config_name, cluster_name)
                        if config_response.success:
                            snaphook_configs.append(config_response.snaphook_config.to_dict())
        
        return {
            "success": True,
            "snaphook_configs": snaphook_configs,
            "message": f"Found {len(snaphook_configs)} SnapHook configurations"
        }
        
    except Exception as e:
        return {
            "success": False,
            "snaphook_configs": [],
            "message": f"Error listing SnapHook configs: {str(e)}"
        }

async def delete_snaphook_config(name: str, cluster_name: str):
    """Delete SnapHook configuration file."""
    
    config_path = f"config/hooks/{cluster_name}/{name}.json"
    
    try:
        if not os.path.exists(config_path):
            return SnapHookConfigResponse(
                success=False,
                message=f"SnapHook config '{name}' not found"
            )
        
        os.remove(config_path)
        
        return SnapHookConfigResponse(
            success=True,
            message=f"SnapHook config '{name}' deleted successfully"
        )
        
    except Exception as e:
        return SnapHookConfigResponse(
            success=False,
            message=f"Error deleting SnapHook config '{name}': {str(e)}"
        )

async def update_snaphook_config_start_time(name: str, cluster_name: str):
    """Update the last_started_at timestamp for a SnapHook config."""
    
    config_path = f"config/hooks/{cluster_name}/{name}.json"
    
    try:
        if not os.path.exists(config_path):
            return SnapHookConfigResponse(
                success=False,
                message=f"SnapHook config '{name}' not found"
            )
        
        # Load existing config
        with open(config_path, "r") as f:
            config_data = json.load(f)
        
        # Update last_started_at
        config_data["snaphook_config_details"]["last_started_at"] = datetime.now().isoformat()
        
        # Save updated config
        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=4)
        
        return SnapHookConfigResponse(
            success=True,
            message=f"SnapHook config '{name}' updated successfully"
        )
        
    except Exception as e:
        return SnapHookConfigResponse(
            success=False,
            message=f"Error updating SnapHook config '{name}': {str(e)}"
        )
