from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os
from typing import List


router = APIRouter()

# Get the base directory (src/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# IMPORTANT: More specific routes must come before parameterized routes
# Otherwise FastAPI will match /runc/versions as /runc/{version} with version="versions"

@router.get("/runc/versions")
async def list_runc_versions() -> List[str]:
    """List all available runc versions"""
    versions = []
    runc_dir = os.path.join(BASE_DIR, "download", "runc")
    
    if os.path.exists(runc_dir):
        for item in os.listdir(runc_dir):
            item_path = os.path.join(runc_dir, item)
            if os.path.isdir(item_path):
                # Check if there's a binary file in this directory
                for root, dirs, files in os.walk(item_path):
                    for file in files:
                        if file == "runc" or file == "runc.amd64":
                            versions.append(item)
                            break
                    if item in versions:
                        break
    
    return sorted(versions, reverse=True)

@router.get("/crio/versions")
async def list_crio_versions() -> List[str]:
    """List all available crio versions"""
    versions = []
    crio_dir = os.path.join(BASE_DIR, "download", "crio")
    
    if os.path.exists(crio_dir):
        for item in os.listdir(crio_dir):
            item_path = os.path.join(crio_dir, item)
            if os.path.isdir(item_path):
                # Check if there's a binary file in this directory
                for root, dirs, files in os.walk(item_path):
                    for file in files:
                        if file.endswith('.rpm') or file.startswith('cri-o') or file.startswith('crio'):
                            versions.append(item)
                            break
                    if item in versions:
                        break
    
    return sorted(versions, reverse=True)

@router.get("/runc/{version}")
async def download_runc(version: str):
    # Try different possible paths for runc binary
    possible_paths = [
        os.path.join(BASE_DIR, "download", "runc", version, "runc")
    ]
    
    for file_path in possible_paths:
        if os.path.exists(file_path):
            return FileResponse(file_path, media_type='application/octet-stream', filename="runc.amd64")
    
    raise HTTPException(status_code=404, detail="File not found")

@router.get("/crio/{version}")
async def download_crio(version: str):
    # Try different possible paths for crio binary
    possible_paths = [
        os.path.join(BASE_DIR, "download", "crio", version, f"cri-o-{version}.rpm")
    ]
    
    for file_path in possible_paths:
        if os.path.exists(file_path):
            filename = os.path.basename(file_path)
            return FileResponse(file_path, media_type='application/octet-stream', filename=filename)
    
    raise HTTPException(status_code=404, detail="File not found")