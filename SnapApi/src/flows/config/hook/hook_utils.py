"""
Utility functions for SnapHook management.
Includes certificate validation and config syncing.
"""

import os
import base64
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from flows.config.hook.save_snaphook_config import save_snaphook_config

logger = logging.getLogger("automation_api")


def is_certificate_valid(ca_bundle: Optional[str]) -> bool:
    """
    Check if a certificate (CA bundle) is valid and not expired.
    
    Args:
        ca_bundle: Base64-encoded CA bundle string
        
    Returns:
        bool: True if certificate is valid, False otherwise
    """
    if not ca_bundle:
        logger.warning("[HookUtils] No CA bundle provided, certificate is invalid")
        return False
    
    try:
        # Decode base64 CA bundle
        try:
            cert_bytes = base64.b64decode(ca_bundle)
        except Exception as e:
            logger.error(f"[HookUtils] Failed to decode CA bundle: {e}")
            return False
        
        # Parse certificate
        try:
            cert = x509.load_pem_x509_certificate(cert_bytes, default_backend())
        except Exception as e:
            logger.error(f"[HookUtils] Failed to parse certificate: {e}")
            return False
        
        # Check if certificate is expired
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        
        # Get certificate validity dates (using UTC-aware properties)
        not_valid_after = cert.not_valid_after_utc
        not_valid_before = cert.not_valid_before_utc
        
        if now >= not_valid_after:
            logger.warning(f"[HookUtils] Certificate expired on {not_valid_after}, current time: {now}")
            return False
        
        # Check if certificate is not yet valid
        if now < not_valid_before:
            logger.warning(f"[HookUtils] Certificate not yet valid (valid from {not_valid_before}), current time: {now}")
            return False
        
        logger.info(f"[HookUtils] Certificate is valid (expires on {not_valid_after})")
        return True
        
    except Exception as e:
        logger.error(f"[HookUtils] Error validating certificate: {e}")
        return False


def verify_certificate_matches_server(ca_bundle: Optional[str]) -> bool:
    """
    Verify that the CA bundle in the webhook matches the certificate being served by the shared HTTPS server.
    This detects certificate mismatches that cause "certificate signed by unknown authority" errors.
    
    Args:
        ca_bundle: Base64-encoded CA bundle string from webhook configuration
        
    Returns:
        bool: True if certificates match, False if there's a mismatch
    """
    if not ca_bundle:
        logger.warning("[HookUtils] No CA bundle provided, cannot verify certificate match")
        return False
    
    try:
        from classes.shared_https_server import shared_https_server
        
        # Get the current certificate from the shared HTTPS server
        if not shared_https_server or not shared_https_server.is_running:
            logger.warning("[HookUtils] Shared HTTPS server not running, cannot verify certificate match")
            return False
        
        server_ca_bundle = shared_https_server.get_ca_bundle()
        if not server_ca_bundle:
            logger.warning("[HookUtils] Shared HTTPS server has no CA bundle, cannot verify certificate match")
            return False
        
        # Decode both certificates
        try:
            webhook_cert_bytes = base64.b64decode(ca_bundle)
            server_cert_bytes = server_ca_bundle.encode('utf-8')
        except Exception as e:
            logger.error(f"[HookUtils] Failed to decode certificates for comparison: {e}")
            return False
        
        # Parse both certificates
        try:
            webhook_cert = x509.load_pem_x509_certificate(webhook_cert_bytes, default_backend())
            server_cert = x509.load_pem_x509_certificate(server_cert_bytes, default_backend())
        except Exception as e:
            logger.error(f"[HookUtils] Failed to parse certificates for comparison: {e}")
            return False
        
        # Compare certificate serial numbers and fingerprints
        webhook_serial = webhook_cert.serial_number
        server_serial = server_cert.serial_number
        
        # Also compare certificate fingerprints (SHA256)
        from cryptography.hazmat.primitives import hashes
        webhook_fingerprint = webhook_cert.fingerprint(hashes.SHA256())
        server_fingerprint = server_cert.fingerprint(hashes.SHA256())
        
        if webhook_serial == server_serial and webhook_fingerprint == server_fingerprint:
            logger.info("[HookUtils] Certificate in webhook matches server certificate")
            return True
        else:
            logger.warning(
                f"[HookUtils] Certificate mismatch detected! "
                f"Webhook serial: {webhook_serial}, Server serial: {server_serial}, "
                f"Webhook fingerprint: {webhook_fingerprint.hex()}, Server fingerprint: {server_fingerprint.hex()}"
            )
            return False
            
    except Exception as e:
        logger.error(f"[HookUtils] Error verifying certificate match: {e}")
        # If we can't verify, assume there's a mismatch to be safe
        return False


async def sync_hook_to_config(
    name: str,
    cluster_name: str,
    cluster_config: Dict[str, Any],
    webhook_url: Optional[str] = None,
    namespace: str = "snap",
    cert_expiry_days: int = 365
) -> bool:
    """
    Sync hook configuration to config/hooks folder for backup.
    
    Args:
        name: Hook name
        cluster_name: Cluster name
        cluster_config: Cluster configuration dict
        webhook_url: Webhook URL
        namespace: Namespace
        cert_expiry_days: Certificate expiry days
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"[HookUtils] Syncing hook '{name}' to config folder for backup")
        
        # Use save_snaphook_config which handles file creation/updates
        # First check if file exists, if so update it, otherwise create it
        config_dir = f"config/hooks/{cluster_name}"
        config_path = f"{config_dir}/{name}.json"
        
        if os.path.exists(config_path):
            # Update existing config
            import json
            with open(config_path, "r") as f:
                config_data = json.load(f)
            
            # Update the config data
            config_data["snaphook_config_details"]["webhook_url"] = webhook_url
            config_data["snaphook_config_details"]["namespace"] = namespace
            config_data["snaphook_config_details"]["cert_expiry_days"] = cert_expiry_days
            config_data["cluster_config"] = cluster_config
            
            # Save updated config
            os.makedirs(config_dir, exist_ok=True)
            with open(config_path, "w") as f:
                json.dump(config_data, f, indent=4)
            
            logger.info(f"[HookUtils] Updated hook config '{name}' in config folder")
        else:
            # Create new config
            result = await save_snaphook_config(
                name=name,
                cluster_name=cluster_name,
                cluster_config=cluster_config,
                webhook_url=webhook_url,
                namespace=namespace,
                cert_expiry_days=cert_expiry_days
            )
            
            if not result.success:
                logger.warning(f"[HookUtils] Failed to save hook config: {result.message}")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"[HookUtils] Error syncing hook to config folder: {e}")
        return False

