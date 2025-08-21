from pydantic import BaseModel
from typing import Optional
import os

class UpdatePlaybookRequest(BaseModel):
    filename: str
    content: str

class UpdatePlaybookResponse(BaseModel):
    success: bool
    message: str
    filename: Optional[str] = None

async def update_playbook_config(request: UpdatePlaybookRequest):
    try:
        # Validate filename ends with .yaml
        if not request.filename.endswith('.yaml'):
            return UpdatePlaybookResponse(
                success=False,
                message="Filename must end with .yaml",
                filename=None
            )

        # Construct full file path
        file_path = os.path.join("playbook", request.filename)

        # Check if file exists
        if not os.path.exists(file_path):
            return UpdatePlaybookResponse(
                success=False,
                message=f"File {request.filename} does not exist",
                filename=None
            )

        # Write the new content to the file
        with open(file_path, 'w') as f:
            f.write(request.content)

        return UpdatePlaybookResponse(
            success=True,
            message=f"Successfully updated {request.filename}",
            filename=request.filename
        )

    except Exception as e:
        return UpdatePlaybookResponse(
            success=False,
            message=f"Error updating file: {str(e)}",
            filename=None
        ) 