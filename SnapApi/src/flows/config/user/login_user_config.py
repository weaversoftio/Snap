import os
import json
from classes.userconfig import UserConfig, LoginUserConfigRequest
import jwt
from datetime import datetime, timedelta
from typing import Optional
import logging
from services.ad_auth_service import ADAuthService

# Load the keys
with open("config/security/private.pem", "rb") as f:
    PRIVATE_KEY = f.read()
with open("config/security/public.pem", "rb") as f:
    PUBLIC_KEY = f.read()

ALGORITHM = "RS256"  # Changed to RSA algorithm

logger = logging.getLogger("automation_api")

async def login_user_config(request: LoginUserConfigRequest):
    """
    Login with support for both AD and local authentication
    auth_method: 'ad' (AD only) or 'local' (local only)
    """
    auth_method = getattr(request, 'auth_method', 'local') or 'local'
    
    # If auth_method is 'ad', try AD authentication
    if auth_method == 'ad':
        try:
            logger.info(f"[Login] Attempting AD authentication for user '{request.username}'")
            
            # Try AD authentication using app-level config
            ad_result = ADAuthService.authenticate_and_authorize(
                username=request.username,
                password=request.password
            )
            
            # If AD authentication succeeded and access granted
            if ad_result.get('success') and ad_result.get('access_granted'):
                logger.info(f"[Login] AD authentication successful for user '{request.username}'")
                user_cn = ad_result.get('user_cn', request.username)
                user_data = {
                    "username": request.username,
                    "name": user_cn,
                    "role": "user"  # Default role for AD users
                }
                # Store username and name in token for verification
                token_data = {
                    "username": request.username,
                    "name": user_cn,
                    "auth_method": "ad"
                }
                return {
                    "success": True,
                    "user": user_data,
                    "token": create_access_token(data=token_data, expires_delta=timedelta(days=1)),
                    "auth_method": "ad"
                }
            
            # AD authentication failed
            logger.warning(f"[Login] AD authentication failed for user '{request.username}'")
            return {
                "success": False,
                "message": ad_result.get('message', 'Active Directory authentication failed')
            }
        except Exception as e:
            logger.error(f"[Login] Error during AD authentication attempt: {e}")
            return {
                "success": False,
                "message": f"Active Directory authentication error: {str(e)}"
            }
    
    # Local user authentication
    logger.info(f"[Login] Attempting local authentication for user '{request.username}'")
    path = f"config/security/users/{request.username}.json"

    if not os.path.exists(path):
        return {"success": False, "message": "Local user not found"}

    with open(os.path.join(path), "r") as f:
        user_data = json.load(f)

        if (user_data.get("userdetails", {}).get("username") == request.username and 
            user_data.get("userdetails", {}).get("password") == request.password):
            user_data = {
                "username": user_data["userdetails"]["username"],
                "name": user_data["userdetails"]["name"],
                "role": user_data["userdetails"]["role"]
            }
            return {
                "success": True,
                "user": user_data,
                "token": create_access_token(data={"username": request.username}, expires_delta=timedelta(days=1)),
                "auth_method": "local"
            }

    return {"success": False, "message": "Invalid password for local user"}

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    print("create_access_token", data)
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, PRIVATE_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str):
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("username")
        if username is None:
            return None
        return username
    except Exception as e:
        return None