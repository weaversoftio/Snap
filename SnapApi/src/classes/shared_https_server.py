import ssl
import tempfile
import os
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional
import json

logger = logging.getLogger(__name__)

class SharedWebhookHandler(BaseHTTPRequestHandler):
    """Webhook handler for the shared HTTPS server."""
    
    def log_message(self, format, *args):
        logger.info(f"Shared HTTPS Server: {format % args}")
    
    def do_POST(self):
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            # Parse JSON
            try:
                body = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return
            
            # Route to appropriate hook handler
            response = self._route_to_hook(body)
            
            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Error in shared webhook handler: {e}")
            self.send_error(500, str(e))
    
    def _route_to_hook(self, body):
        """Route webhook request to the appropriate hook handler."""
        try:
            # Extract hook information from the request
            hook_name = self._determine_hook_from_request(body)
            
            if hook_name and hasattr(self, 'server_manager') and hook_name in self.server_manager.hook_handlers:
                handler_info = self.server_manager.hook_handlers[hook_name]
                return handler_info['handler'](body)
            else:
                # Log available handlers for debugging
                if hasattr(self, 'server_manager'):
                    available_handlers = list(self.server_manager.hook_handlers.keys())
                    logger.warning(f"No handler found for hook: {hook_name}. Available handlers: {available_handlers}")
                else:
                    logger.warning("No server manager available")
                
                # Default handling or error
                return {
                    "apiVersion": "admission.k8s.io/v1",
                    "kind": "AdmissionReview",
                    "response": {
                        "uid": body.get("request", {}).get("uid", ""),
                        "allowed": True,
                        "status": {
                            "message": f"No handler found for hook: {hook_name}"
                        }
                    }
                }
                
        except Exception as e:
            logger.error(f"Error routing to hook: {e}")
            return {
                "apiVersion": "admission.k8s.io/v1",
                "kind": "AdmissionReview",
                "response": {
                    "uid": body.get("request", {}).get("uid", ""),
                    "allowed": False,
                    "status": {
                        "message": f"Error processing webhook: {str(e)}"
                    }
                }
            }
    
    def _determine_hook_from_request(self, body):
        """Determine which hook should handle this request."""
        try:
            # Get the request object
            request = body.get("request", {})
            
            # Method 1: Check if there's a webhook name in the request metadata
            if "webhook" in request:
                return request["webhook"]
            
            # Method 2: Check the webhook configuration name from the request
            # This comes from the Kubernetes webhook configuration
            webhook_config_name = request.get("webhookConfigurationName")
            if webhook_config_name:
                # Extract hook name from webhook config name (format: snaphook-{hook_name}-{cluster_name})
                if webhook_config_name.startswith("snaphook-"):
                    parts = webhook_config_name.split("-")
                    if len(parts) >= 3:
                        hook_name = parts[1]  # Extract the hook name
                        if hasattr(self, 'server_manager') and hook_name in self.server_manager.hook_handlers:
                            return hook_name
            
            # Method 3: Check the webhook name from the admission request
            webhook_name = request.get("webhookName")
            if webhook_name:
                # Extract hook name from webhook name (format: snaphook-{hook_name}.weaversoft.io)
                if webhook_name.startswith("snaphook-") and ".weaversoft.io" in webhook_name:
                    hook_name = webhook_name.split("-")[1].split(".")[0]
                    if hasattr(self, 'server_manager') and hook_name in self.server_manager.hook_handlers:
                        return hook_name
            
            # Method 4: For backward compatibility, use the first available hook
            if hasattr(self, 'server_manager') and self.server_manager.hook_handlers:
                available_hooks = list(self.server_manager.hook_handlers.keys())
                return available_hooks[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error determining hook from request: {e}")
            return None

class SharedHTTPServerManager:
    """
    Manages a shared HTTPS server for multiple SnapHook instances.
    All hooks share the same certificates and port.
    """
    
    def __init__(self):
        self.https_server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.cert_data: Optional[Dict[str, str]] = None
        self.ca_bundle: Optional[str] = None
        self.hook_handlers: Dict[str, Any] = {}  # hook_name -> handler info
        self._lock = threading.Lock()
    
    def generate_shared_certificates(self) -> Dict[str, str]:
        """
        Generate shared self-signed certificates for all hooks.
        
        Returns:
            Dict containing certificate data
        """
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from datetime import datetime, timedelta
        import ipaddress
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Create certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SnapAPI"),
            x509.NameAttribute(NameOID.COMMON_NAME, "snaphook.weaversoft.io"),
        ])
        
        # Add Subject Alternative Names
        san_list = [
            x509.DNSName("snaphook.weaversoft.io"),
            x509.DNSName("localhost"),
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        ]
        
        # Add additional IPs if needed
        try:
            san_list.append(x509.IPAddress(ipaddress.IPv4Address("192.168.33.209")))
        except:
            pass
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName(san_list),
            critical=False,
        ).sign(private_key, hashes.SHA256())
        
        # Serialize certificate and key
        cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')
        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        return {
            "cert": cert_pem,
            "key": key_pem,
            "cert_data": cert_pem,
            "key_data": key_pem
        }
    
    def start_shared_server(self) -> bool:
        """
        Start the shared HTTPS server.
        
        Returns:
            bool: True if successful, False otherwise
        """
        with self._lock:
            if self.is_running:
                logger.info("Shared HTTPS server is already running")
                return True
            
            try:
                # Generate shared certificates
                self.cert_data = self.generate_shared_certificates()
                self.ca_bundle = self.cert_data["cert"]
                
                # Create SSL context
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                
                # Create temporary files for certificates
                with tempfile.NamedTemporaryFile(mode='w', suffix='.crt', delete=False) as f:
                    f.write(self.cert_data["cert_data"])
                    cert_file = f.name
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.key', delete=False) as f:
                    f.write(self.cert_data["key_data"])
                    key_file = f.name
                
                try:
                    ssl_context.load_cert_chain(cert_file, key_file)
                    
                    # Create HTTPS server with shared handler
                    handler = self._create_shared_webhook_handler()
                    self.https_server = HTTPServer(('0.0.0.0', 8443), handler)
                    self.https_server.socket = ssl_context.wrap_socket(
                        self.https_server.socket, 
                        server_side=True
                    )
                    
                    # Start server in background thread
                    self.server_thread = threading.Thread(target=self._run_server, daemon=True)
                    self.server_thread.start()
                    
                    # Wait a moment for server to start
                    import time
                    time.sleep(1)
                    
                    self.is_running = True
                    logger.info("Shared HTTPS server started on port 8443")
                    return True
                    
                finally:
                    # Clean up temporary files
                    os.unlink(cert_file)
                    os.unlink(key_file)
                    
            except Exception as e:
                logger.error(f"Failed to start shared HTTPS server: {e}")
                return False
    
    def _run_server(self):
        """Run the HTTPS server in the background thread."""
        try:
            self.https_server.serve_forever()
        except Exception as e:
            logger.error(f"Shared HTTPS server error: {e}")
        finally:
            self.is_running = False
    
    def _create_shared_webhook_handler(self):
        """Create the shared webhook handler that routes to specific hooks."""
        # Set the server manager reference
        SharedWebhookHandler.server_manager = self
        return SharedWebhookHandler
    
    def register_hook_handler(self, hook_name: str, handler_func):
        """
        Register a hook handler with the shared server.
        
        Args:
            hook_name: Unique name for the hook
            handler_func: Function to handle webhook requests for this hook
        """
        with self._lock:
            self.hook_handlers[hook_name] = {
                'handler': handler_func,
                'registered_at': threading.current_thread().ident
            }
            logger.info(f"Registered hook handler: {hook_name}")
    
    def unregister_hook_handler(self, hook_name: str):
        """
        Unregister a hook handler from the shared server.
        
        Args:
            hook_name: Name of the hook to unregister
        """
        with self._lock:
            if hook_name in self.hook_handlers:
                del self.hook_handlers[hook_name]
                logger.info(f"Unregistered hook handler: {hook_name}")
    
    def stop_shared_server(self) -> bool:
        """
        Stop the shared HTTPS server.
        
        Returns:
            bool: True if successful, False otherwise
        """
        with self._lock:
            if not self.is_running:
                logger.info("Shared HTTPS server is not running")
                return True
            
            try:
                if self.https_server:
                    self.https_server.shutdown()
                    self.https_server.server_close()
                    self.is_running = False
                    logger.info("Shared HTTPS server stopped")
                
                # Wait for server thread to finish
                if self.server_thread and self.server_thread.is_alive():
                    self.server_thread.join(timeout=2)
                    if self.server_thread.is_alive():
                        logger.warning("Server thread did not stop gracefully")
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to stop shared HTTPS server: {e}")
                return False
    
    def get_ca_bundle(self) -> str:
        """Get the CA bundle for webhook configurations."""
        return self.ca_bundle or ""
    
    def get_cert_data(self) -> Dict[str, str]:
        """Get the certificate data."""
        return self.cert_data or {}

# Global shared server instance
shared_https_server = SharedHTTPServerManager()