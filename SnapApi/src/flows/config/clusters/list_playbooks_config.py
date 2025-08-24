from pydantic import BaseModel
from typing import List
import os

class PlaybookConfigDetails(BaseModel):
    name: str
    data: str

class PlaybookConfigsResponse(BaseModel):
    success: bool
    message: str
    config_list: List[PlaybookConfigDetails]

async def list_playbooks_config():
    path = f"playbook"
    yaml_files = []
    for file in os.listdir(path):
        if file.endswith(".yaml"):
            #Read the yaml file
            with open(os.path.join(path, file), "r") as f:
                print("list_playbooks_config file", file)
                try:
                    # Read the raw YAML content as string
                    yaml_content = f.read()
                    # Store the YAML content and file name in PlaybookConfigDetails
                    config_details = PlaybookConfigDetails(
                        name=file,
                        data=yaml_content
                    )
                    # Add the config details to the list
                    yaml_files.append(config_details)
                except Exception as e:
                    print(f"Error loading playbook config file {file}: {e}")

    return PlaybookConfigsResponse(
        success=True,
        message="Cluster configs listed successfully",
        config_list=yaml_files
    )
    

