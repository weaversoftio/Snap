import os
import json
from classes.userconfig import VerifyUserConfigRequest
import jwt
from datetime import datetime, timedelta
from typing import Optional

# Load the RSA keys
with open("config/security/private.pem", "rb") as f:
    PRIVATE_KEY = f.read()
with open("config/security/public.pem", "rb") as f:
    PUBLIC_KEY = f.read()

ALGORITHM = "RS256"  # Changed to RSA algorithm

def verify_user_config(token: str):
    # Decode token once to get username and other data
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("username")
        if username is None:
            return {"success": False, "message": "Invalid token: missing username"}
    except jwt.ExpiredSignatureError:
        return {"success": False, "message": "Token has expired"}
    except jwt.InvalidTokenError as e:
        return {"success": False, "message": f"Invalid token: {str(e)}"}
    except Exception as e:
        return {"success": False, "message": f"Token verification error: {str(e)}"}
    
    path = f"config/security/users/{username}.json"
    
    # If local user file exists, use it (local user)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                user_config = json.load(f)

            user_data = {
                "username": user_config["userdetails"]["username"],
                "name": user_config["userdetails"]["name"],
                "role": user_config["userdetails"]["role"]
            }

            return {"success": True, "user": user_data}
        except Exception as e:
            return {"success": False, "message": f"Error reading user config: {str(e)}"}
    
    # If no local user file exists but token is valid, treat as AD user
    # Get name from token payload if available
    user_name = payload.get("name", username)
    
    user_data = {
        "username": username,
        "name": user_name,
        "role": "user"  # Default role for AD users
    }
    
    return {"success": True, "user": user_data}

def verify_token(token: str):
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("username")
        if username is None:
            return None
        return username
    except Exception as e:
        return None