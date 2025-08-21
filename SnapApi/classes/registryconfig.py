from pydantic import BaseModel
import os
import json 
from flows.proccess_utils import run
from typing import Optional

class RegistryConfigDetails(BaseModel):
    registry: str   
    username: str
    password: str

class RegistryConfig(BaseModel):
    registry_config_details: RegistryConfigDetails
    name: str

    def __init__(self, registry_config_details: RegistryConfigDetails, name: str):
        super().__init__(registry_config_details=registry_config_details, name=name)
    
    def to_dict(self):
        return {
            "registry_config_details": self.registry_config_details.model_dump(),
            "name": self.name
        }

async def login_to_registry(registry_config_name: str):
    try:
        # Get the registry config details from the config folder
        path = f"config/registry/{registry_config_name}.json"
        #check if the file exists
        if not os.path.exists(path):
            return {"success": False, "message": "Registry config not found"}

        with open(path, "r") as f:
            try:
                data = json.load(f)
                registry=data["registry_config_details"]["registry"]
                username=data["registry_config_details"]["username"]
                password=data["registry_config_details"]["password"]
                # Create RegistryConfigDetails object first
                registry_config = RegistryConfigDetails(
                    registry=registry,
                    username=username,
                    password=password
                )
            except Exception as e:
                print(f"Error loading registry config file {registry_config_name}: {e}")

        # Login to the registry
        command = [
            "buildah",
            "login",
            registry_config.registry,
            "--username", registry_config.username,
            "--password", registry_config.password,
            "--tls-verify=false"
        ]
        # Execute the command using the run helper function
        await run(command, capture_output=True, text=True, check=True)

        return {"message": f"Successfully logged in to {registry_config.registry}"}

    except RuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error executing buildah login command: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )

def get_registry(registry_config_name: str) -> Optional[RegistryConfigDetails]:
    try:
        path = f"config/registry/{registry_config_name}.json"
        if not os.path.exists(path):
            print("Registry config not found")
            return None

        with open(path, "r") as f:
            try:
                data = json.load(f)
                registry = data["registry_config_details"]["registry"]
                username = data["registry_config_details"]["username"]
                password = data["registry_config_details"]["password"]

                return RegistryConfigDetails(
                    registry=registry,
                    username=username,
                    password=password
                )

            except Exception as e:
                print(f"Error parsing registry config file {registry_config_name}: {e}")
                return None
    except Exception as e:
        print(f"Error loading registry config file {registry_config_name}: {e}")
        return None

