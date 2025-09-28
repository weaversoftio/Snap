from pydantic import BaseModel
from classes.registryconfig import RegistryConfig, RegistryConfigDetails
import os
import json
from flows.config.registry.create_registry_config import RegistryConfigRequest
from typing import List

class RegistryConfigResponse(BaseModel):
    success: bool
    message: str
    registry_configs: List[RegistryConfig]

async def list_registry_config():
    # get all the registry configs from the config folder in the registry config directory
    path = f"config/registry"
    registry_configs = []
    
    # Check if directory exists
    if not os.path.exists(path):
        return RegistryConfigResponse(
            success=True,
            message="No registry configs found - directory does not exist",
            registry_configs=registry_configs
        )
    
    try:
        for file in os.listdir(path):
            if file.endswith(".json"):
                #Read the json file
                with open(os.path.join(path, file), "r") as f:
                    try:
                        data = json.load(f)
                        # Create RegistryConfigDetails object first
                        registry_details = RegistryConfigDetails(
                            registry=data["registry_config_details"]["registry"],
                            username=data["registry_config_details"]["username"],
                            password=data["registry_config_details"]["password"]
                        )
                        # Create RegistryConfig with the details
                        config = RegistryConfig(
                            registry_config_details=registry_details,
                            name=data["name"]
                        )
                        registry_configs.append(config)
                    except Exception as e:
                        print(f"Error loading registry config file {file}: {e}")
    except Exception as e:
        print(f"Error accessing registry config directory {path}: {e}")
        return RegistryConfigResponse(
            success=False,
            message=f"Error accessing registry config directory: {str(e)}",
            registry_configs=[]
        )

    return RegistryConfigResponse(
        success=True,
        message="Registry configs listed successfully",
        registry_configs=registry_configs
    )
    