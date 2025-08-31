import jwt  # PyJWT library
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from flows.config.user.verify_user_config import verify_user_config
from typing import Callable
import os
import base64
import json

def _is_kubernetes_service_account_token(token: str) -> bool:
    """
    Check if the token is a Kubernetes service account token.
    K8s service account tokens are JWT tokens but have specific characteristics.
    """
    try:
        # Decode the token without verification to check its structure
        parts = token.split('.')
        if len(parts) != 3:
            return False
        
        # Decode the payload (second part)
        payload = parts[1]
        # Add padding if needed
        payload += '=' * (4 - len(payload) % 4)
        decoded_payload = base64.urlsafe_b64decode(payload)
        token_data = json.loads(decoded_payload)
        
        # Check for Kubernetes service account token characteristics
        return (
            token_data.get('iss') == 'kubernetes/serviceaccount' or
            'kubernetes.io/serviceaccount' in token_data.get('sub', '') or
            'system:serviceaccount' in token_data.get('sub', '')
        )
    except Exception:
        return False

def verify_token(request: Request):
    token = request.headers.get("Authorization")
    if token and token.startswith("Bearer "):
        token = token.replace("Bearer ", "")
        
        # Check if this is a Kubernetes service account token
        if _is_kubernetes_service_account_token(token):
            print("[auth] Detected Kubernetes service account token, allowing access")
            # For service account tokens, return a service account identifier
            return "system:serviceaccount"
        
        # Handle regular JWT tokens for users
        result = verify_user_config(token)
        if (result.get("success") == False):
            raise HTTPException(status_code=401, detail="Invalid or Expired token")

        username = result["user"]["username"]
        return username
        
    else:
        return None
