"""
SnapHook - Kubernetes Mutating Webhook for Snap API.
Implements a class that creates MutatingWebhookConfiguration and HTTPS listener.
"""

import os
import ssl
import base64
import logging
import subprocess
import tempfile
import threading
import asyncio
import warnings
from typing import Dict, Any, Optional
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from kubernetes import client
from kubernetes.client.rest import ApiException
import urllib3

# Suppress urllib3 InsecureRequestWarning for Kubernetes client
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Import shared server (will be available after module loads)
try:
    from classes.shared_https_server import shared_https_server
except ImportError:
    shared_https_server = None

logger = logging.getLogger("automation_api")


class SnapHook:
    """
    SnapHook class that creates MutatingWebhookConfiguration and HTTPS listener.
    
    When instantiated:
    1. Creates a MutatingWebhookConfiguration
    2. Starts an HTTPS listener (router) for the webhook endpoint (/mutate)
    3. Uses self-signed TLS certificates
    4. Provides CA bundle in the webhook configuration
    """
    
    def __init__(self, name: str, cluster_name: str, cluster_config, webhook_url: str = None, 
                 namespace: str = "snap", cert_expiry_days: int = 365):
        """
        Initialize SnapHook.
        
        Args:
            name: Name of the SnapHook instance
            cluster_name: Name of the cluster
            cluster_config: Cluster configuration containing API URL and token
            webhook_url: External URL for the webhook (e.g., "https://snap.mycompany.com/mutate")
            namespace: Kubernetes namespace for webhook resources
            cert_expiry_days: Certificate validity period in days
        """
        self.name = name
        self.cluster_name = cluster_name
        self.cluster_config = cluster_config
        self.namespace = namespace
        self.cert_expiry_days = cert_expiry_days
        # Auto-generate webhook URL from SNAP_API_URL if not provided
        if webhook_url:
            self.webhook_url = webhook_url
        else:
            self.webhook_url = self._generate_webhook_url()
        
        # Note: Certificate data and HTTPS server are now managed by SharedHTTPServerManager
        self.is_running = False
        self.cert_data = None
        self.ca_bundle = None
        
        # Kubernetes client
        self.kube_client = None
        self._setup_kubernetes_config()
    
    def _generate_webhook_url(self) -> str:
        """
        Generate webhook URL from SNAP_API_URL environment variable.
        
        Returns:
            Generated webhook URL
        """
        import os
        snap_api_url = os.getenv("SNAP_API_URL", "http://localhost:8000")
        
        # Extract host and port from SNAP_API_URL
        if snap_api_url.startswith("http://"):
            host_port = snap_api_url.replace("http://", "")
        elif snap_api_url.startswith("https://"):
            host_port = snap_api_url.replace("https://", "")
        else:
            host_port = snap_api_url
        
        # Split host and port
        if ":" in host_port:
            host, port = host_port.split(":", 1)
        else:
            host = host_port
            port = "8000"  # Default API port
        
        # Use port 8443 for webhook (SnapHook HTTPS server port)
        webhook_url = f"https://{host}:8443/mutate"
        
        logger.info(f"SnapHook: Auto-generated webhook URL: {webhook_url}")
        return webhook_url
    
    def _setup_kubernetes_config(self) -> None:
        """Setup Kubernetes client configuration."""
        try:
            kube_config = client.Configuration()
            kube_config.host = self.cluster_config.cluster_config_details.kube_api_url
            kube_config.api_key = {'authorization': f'Bearer {self.cluster_config.cluster_config_details.token}'}
            
            # SSL configuration - check environment variable for verification control
            verify_ssl = os.getenv('KUBE_VERIFY_SSL', 'false').lower() == 'true'
            kube_config.verify_ssl = verify_ssl
            
            if not verify_ssl:
                # Create SSL context that doesn't verify certificates
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                kube_config.ssl_ca_cert = None
                kube_config.cert_file = None
                kube_config.key_file = None
                logger.info(f"SnapHook: SSL verification disabled for cluster {self.cluster_name}")
            else:
                logger.info(f"SnapHook: SSL verification enabled for cluster {self.cluster_name}")
            
            self.kube_client = client.ApiClient(kube_config)
            logger.info(f"SnapHook: Configured Kubernetes client for cluster {self.cluster_name}")
        except Exception as e:
            logger.error(f"SnapHook: Could not setup Kubernetes configuration: {e}")
            raise
    
    def _generate_self_signed_certificates(self) -> Dict[str, str]:
        """
        Generate self-signed certificates for HTTPS webhook.
        
        Returns:
            Dict containing certificate data
        """
        try:
            logger.info("SnapHook: Generating self-signed certificates...")
            
            # Create temporary directory for certificate files
            with tempfile.TemporaryDirectory() as temp_dir:
                cert_file = os.path.join(temp_dir, "tls.crt")
                key_file = os.path.join(temp_dir, "tls.key")
                csr_file = os.path.join(temp_dir, "csr.conf")
                
                # Create CSR configuration
                csr_config = self._create_csr_config()
                with open(csr_file, "w") as f:
                    f.write(csr_config)
                
                # Generate private key and certificate
                cmd = [
                    "openssl", "req", "-x509", "-newkey", "rsa:2048",
                    "-keyout", key_file,
                    "-out", cert_file,
                    "-days", str(self.cert_expiry_days),
                    "-nodes",
                    "-config", csr_file,
                    "-extensions", "req_ext"
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                
                # Read generated files
                with open(cert_file, "rb") as f:
                    cert_data = f.read()
                
                with open(key_file, "rb") as f:
                    key_data = f.read()
                
                # Encode in base64 for Kubernetes
                cert_b64 = base64.b64encode(cert_data).decode('utf-8')
                key_b64 = base64.b64encode(key_data).decode('utf-8')
                
                logger.info("SnapHook: Successfully generated self-signed certificates")
                
                return {
                    "cert": cert_b64,
                    "key": key_b64,
                    "cert_data": cert_data.decode('utf-8'),
                    "key_data": key_data.decode('utf-8'),
                    "expiry_days": self.cert_expiry_days,
                    "generated_at": datetime.now().isoformat()
                }
                
        except subprocess.CalledProcessError as e:
            logger.error(f"SnapHook: OpenSSL command failed: {e.stderr}")
            raise
        except Exception as e:
            logger.error(f"SnapHook: Certificate generation failed: {e}")
            raise
    
    def _create_csr_config(self) -> str:
        """
        Create OpenSSL CSR configuration with proper SANs.
        
        Returns:
            CSR configuration content
        """
        # Extract hostname from webhook URL
        webhook_host = self.webhook_url.replace("https://", "").replace("http://", "").split("/")[0]
        
        # Generate all possible DNS names for the webhook
        dns_names = [
            webhook_host,
            "localhost",
            "127.0.0.1",
            f"snaphook.{self.namespace}.svc",
            f"snaphook.{self.namespace}.svc.cluster.local",
            f"snaphook.{self.namespace}.svc.cluster",
            f"snaphook.{self.namespace}",
            "snaphook"
        ]
        
        # Add cluster-specific names if cluster name is available
        if self.cluster_name and self.cluster_name != "unknown":
            cluster_suffix = f".{self.cluster_name}.cluster.local"
            dns_names.extend([
                f"snaphook.{self.namespace}.svc{cluster_suffix}",
                f"snaphook.{self.namespace}{cluster_suffix}"
            ])
        
        # Extract IP addresses from SNAP_API_URL and webhook URL
        ip_addresses = []
        try:
            import socket
            import os
            
            # Get IP from SNAP_API_URL environment variable
            snap_api_url = os.getenv("SNAP_API_URL", "http://localhost:8000")
            api_host = snap_api_url.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0]
            
            # Try to resolve IP addresses
            hosts_to_resolve = [api_host, webhook_host]
            
            for host in hosts_to_resolve:
                if host and not host.startswith('snaphook') and not host.startswith('localhost'):
                    try:
                        ip = socket.gethostbyname(host)
                        ip_addresses.append(ip)
                        logger.info(f"SnapHook: Resolved {host} to {ip}")
                    except socket.gaierror:
                        # If host is already an IP address, add it directly
                        try:
                            socket.inet_aton(host)
                            ip_addresses.append(host)
                            logger.info(f"SnapHook: Using IP address directly: {host}")
                        except socket.error:
                            pass
            
            # Add common local IPs as fallback
            ip_addresses.extend([
                "127.0.0.1"
            ])
            
            # Remove duplicates while preserving order
            ip_addresses = list(dict.fromkeys(ip_addresses))
            
            logger.info(f"SnapHook: Generated IP addresses for certificate: {ip_addresses}")
            
        except Exception as e:
            logger.warning(f"SnapHook: Could not extract IP addresses: {e}")
            # Fallback to common IPs
            ip_addresses = ["127.0.0.1"]
        
        # Create DNS names section
        dns_section = "\n".join([f"DNS.{i+1} = {dns}" for i, dns in enumerate(dns_names)])
        
        # Create IP addresses section
        ip_section = "\n".join([f"IP.{i+1} = {ip}" for i, ip in enumerate(ip_addresses)])
        
        csr_config = f"""[req]
default_bits = 2048
prompt = no
default_md = sha256
req_extensions = req_ext
distinguished_name = dn

[dn]
O = SnapHook Webhook
CN = {webhook_host}

[req_ext]
subjectAltName = @alt_names

[alt_names]
{dns_section}
{ip_section}
"""
        return csr_config
    
    def _create_mutating_webhook_configuration(self) -> client.V1MutatingWebhookConfiguration:
        """
        Create MutatingWebhookConfiguration object.
        
        Returns:
            V1MutatingWebhookConfiguration object
        """
        # Use unique webhook name based on hook name and cluster
        webhook_name = f"snaphook-{self.name}-{self.cluster_name}"
        
        webhook_config = client.V1MutatingWebhookConfiguration(
            api_version="admissionregistration.k8s.io/v1",
            kind="MutatingWebhookConfiguration",
            metadata=client.V1ObjectMeta(
                name=webhook_name,
                labels={
                    "app": "snaphook",
                    "component": "webhook",
                    "managed-by": "snapapi",
                    "hook-name": self.name,
                    "cluster-name": self.cluster_name
                }
            ),
            webhooks=[
                client.V1MutatingWebhook(
                    name=f"snaphook-{self.name}.weaversoft.io",
                    admission_review_versions=["v1"],
                    side_effects="None",
                    client_config=client.AdmissionregistrationV1WebhookClientConfig(
                        url=self.webhook_url,
                        ca_bundle=self.ca_bundle
                    ),
                    rules=[
                        client.V1RuleWithOperations(
                            operations=["CREATE"],
                            api_groups=[""],
                            api_versions=["v1"],
                            resources=["pods"]
                        )
                    ],
                    object_selector=client.V1LabelSelector(
                        match_expressions=[
                            client.V1LabelSelectorRequirement(
                                key="snap.weaversoft.io/snap",
                                operator="Exists"
                            ),
                            client.V1LabelSelectorRequirement(
                                key="snap.weaversoft.io/mutated",
                                operator="DoesNotExist"
                            )
                        ]
                    )
                )
            ]
        )
        
        return webhook_config
    
    def _create_webhook_handler(self):
        """Create webhook handler function for shared server."""
        def webhook_handler(body):
            """Handle webhook request for this specific hook."""
            try:
                # Process the webhook request using the existing logic
                return self._process_webhook_request(body)
            except Exception as e:
                logger.error(f"SnapHook '{self.name}': Error processing webhook request: {e}")
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
        return webhook_handler
    
    def _process_webhook_request(self, body):
        """Process webhook request - extracted from the original handler logic."""
        try:
            # Extract admission review from request
            admission_review = body.get("request", {})
            pod_spec = admission_review.get("object", {})
            metadata = pod_spec.get("metadata", {})
            
            # Get pod name - handle both 'name' and 'generateName'
            pod_name = metadata.get("name")
            if not pod_name:
                pod_name = metadata.get("generateName", "unknown")
                if pod_name and pod_name.endswith("-"):
                    pod_name = pod_name[:-1]  # Remove trailing dash from generateName
            
            namespace = admission_review.get("namespace", "default")
            
            print(f"SnapHook '{self.name}': Got request for pod {pod_name}")
            
            # Check if pod needs SnapHook modification
            patches = []
            should_patch_image = False
            generated_image_tag = None
            
            try:
                # Extract pod information
                containers = pod_spec.get("spec", {}).get("containers", [])
                labels = pod_spec.get("metadata", {}).get("labels", {})
                
                # Check if pod has the snap label
                if labels.get("snap.weaversoft.io/snap") == "true":
                    for container in containers:
                        container_name = container.get("name", "unknown")
                        original_image = container.get("image", "")
                        
                        # Extract app name and digest
                        app_name = self._extract_app_name_from_pod(pod_name, labels)
                        orig_image_short_digest = self._extract_digest_from_pod(pod_spec)
                        
                        # Generate new image tag
                        # We need to get registry and repo from cluster cache configuration
                        try:
                            snap_config = self._get_snap_config_from_cluster_cache_api(self.cluster_name)
                            registry = snap_config["cache_registry"]
                            repo = snap_config["cache_repo"]
                        except Exception as e:
                            print(f"SnapHook: Failed to load cluster cache config: {e}")
                            # Fallback to default values
                            registry = "Need.Registry.Here:8081"  # Default registry
                            repo = "Repo.Name.Here"  # Default repo
                        pod_template_hash = labels.get("pod-template-hash", "unknown")
                        
                        generated_image_tag = self._generate_image_tag(
                            registry=registry,
                            repo=repo,
                            cluster=self.cluster_name,
                            namespace=namespace,
                            app=app_name,
                            origImageShortDigest=orig_image_short_digest,
                            PodTemplateHash=pod_template_hash
                        )
                        
                        print(f"SnapHook: Generated image tag: {generated_image_tag}")
                        
                        if generated_image_tag:
                            # Check if image exists in registry using skopeo
                            print(f"SnapHook: Checking if image exists: {generated_image_tag}")
                            image_exists = self._check_image_exists_multi_registry(
                                registry, repo, self.cluster_name, namespace, app_name, 
                                orig_image_short_digest, pod_template_hash
                            )
                            
                            if image_exists:
                                print(f"SnapHook: Image exists, will patch pod")
                                # Create patch for image
                                patch = {
                                    "op": "replace",
                                    "path": f"/spec/containers/{containers.index(container)}/image",
                                    "value": generated_image_tag
                                }
                                patches.append(patch)
                                
                                # Add mutation label
                                mutation_patch = {
                                    "op": "replace",
                                    "path": "/metadata/labels/snap.weaversoft.io~1mutated",
                                    "value": "true"
                                }
                                patches.append(mutation_patch)
                                should_patch_image = True
                            else:
                                print(f"SnapHook: Image does not exist, skipping patch")
                        else:
                            print(f"SnapHook: Failed to generate image tag, skipping patch")
                
                # Create response
                if should_patch_image and patches:
                    # Encode patches as base64
                    import base64
                    patches_json = json.dumps(patches)
                    patches_b64 = base64.b64encode(patches_json.encode('utf-8')).decode('utf-8')
                    
                    print(f"SnapHook '{self.name}': Patched pod {pod_name} with {len(patches)} patches")
                    
                    response = {
                        "apiVersion": "admission.k8s.io/v1",
                        "kind": "AdmissionReview",
                        "response": {
                            "uid": admission_review.get("uid", ""),
                            "allowed": True,
                            "patchType": "JSONPatch",
                            "patch": patches_b64,
                            "status": {
                                "message": f"SnapHook '{self.name}': Successfully patched pod {pod_name} with {len(patches)} patches"
                            }
                        }
                    }
                else:
                    print(f"SnapHook '{self.name}': No patches needed for pod {pod_name}")
                    response = {
                        "apiVersion": "admission.k8s.io/v1",
                        "kind": "AdmissionReview",
                        "response": {
                            "uid": admission_review.get("uid", ""),
                            "allowed": True,
                            "status": {
                                "message": f"SnapHook '{self.name}': No modifications needed for pod {pod_name}"
                            }
                        }
                    }
                
                return response
                
            except Exception as e:
                print(f"❌ ERROR: SnapHook '{self.name}': Error processing pod {pod_name}: {e}")
                return {
                    "apiVersion": "admission.k8s.io/v1",
                    "kind": "AdmissionReview",
                    "response": {
                        "uid": admission_review.get("uid", ""),
                        "allowed": False,
                        "status": {
                            "message": f"SnapHook '{self.name}': Error processing pod: {str(e)}"
                        }
                    }
                }
                
        except Exception as e:
            print(f"❌ ERROR: SnapHook '{self.name}': Error in webhook processing: {e}")
            return {
                "apiVersion": "admission.k8s.io/v1",
                "kind": "AdmissionReview",
                "response": {
                    "uid": body.get("request", {}).get("uid", ""),
                    "allowed": False,
                    "status": {
                        "message": f"SnapHook '{self.name}': Error processing webhook: {str(e)}"
                    }
                }
            }
    
    def _create_webhook_handler_old(self):
        """Create HTTP request handler for webhook endpoint."""
        snaphook_instance = self  # Capture the SnapHook instance
        
        class WebhookHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                # Handle query parameters by splitting on '?'
                path = self.path.split('?')[0]
                if path == '/mutate':
                    self._handle_mutate_request()
                else:
                    self._send_error_response(404, "Not Found")
            
            def _handle_mutate_request(self):
                """Handle Kubernetes admission webhook requests."""
                print(f"SnapHook: Received webhook request from {self.client_address[0]}")
                try:
                    # Read request body
                    content_length = int(self.headers.get('Content-Length', 0))
                    post_data = self.rfile.read(content_length)
                    
                    # Parse JSON request
                    request_data = json.loads(post_data.decode('utf-8'))
                    
                    logger.info(f"SnapHook: Received webhook request for pod mutation")
                    
                    # Extract admission review from request
                    admission_review = request_data.get("request", {})
                    pod_spec = admission_review.get("object", {})
                    pod_name = pod_spec.get("metadata", {}).get("name", "unknown")
                    namespace = admission_review.get("namespace", "default")
                    
                    logger.info(f"SnapHook: Processing pod {pod_name} in namespace {namespace}")
                    
                    # Check if pod needs SnapHook modification
                    patches = []
                    should_patch_image = False
                    generated_image_tag = None
                    
                    try:
                        # Extract pod information
                        containers = pod_spec.get("spec", {}).get("containers", [])
                        
                        if containers:
                            # Get the first container's image for analysis
                            first_container = containers[0]
                            original_image = first_container.get("image", "")
                            
                            # Extract pod metadata
                            meta = pod_spec.get("metadata", {}) or {}
                            namespace = meta.get("namespace", "unknown")
                            labels = meta.get("labels", {}) or {}
                            pod_name = meta.get("name", "unknown")
                            
                            # If pod_name is "unknown", try to use generateName
                            if pod_name == "unknown":
                                generate_name = meta.get("generateName", "")
                                if generate_name:
                                    # Remove trailing dash from generateName
                                    pod_name = generate_name.rstrip("-")
                                    print(f"SnapHook: Using generateName: '{generate_name}' -> pod_name: '{pod_name}'")
                            
                            # Extract app name from pod metadata
                            app_name = snaphook_instance._extract_app_name_from_pod(pod_name, labels)
                            pod_template_hash = labels.get("pod-template-hash", "unknown")
                            
                            print(f"SnapHook: Processing pod {pod_name} in namespace {namespace}, app: {app_name}")
                            
                            # Extract digest from original image
                            orig_image_short_digest = snaphook_instance._extract_digest_from_pod(pod_spec)
                            
                            # Get registry and repo from cluster cache configuration
                            try:
                                snap_config = snaphook_instance._get_snap_config_from_cluster_cache_api(snaphook_instance.cluster_name)
                                cache_registry = snap_config["cache_registry"]
                                cache_repo = snap_config["cache_repo"]
                            except Exception as e:
                                print(f"SnapHook: Failed to load cluster cache config: {e}")
                                # Fallback to environment variables
                                cache_registry = os.getenv("snap_registry", "docker.io")
                                cache_repo = os.getenv("snap_repo", "snap")
                            
                            # Generate the complete image tag
                            try:
                                generated_image_tag = snaphook_instance._generate_image_tag(
                                    registry=cache_registry,
                                    repo=cache_repo,
                                    cluster=snaphook_instance.cluster_name,
                                    namespace=namespace,
                                    app=app_name,
                                    origImageShortDigest=orig_image_short_digest,
                                    PodTemplateHash=pod_template_hash
                                )
                            except Exception as tag_error:
                                print(f"SnapHook: Failed to generate image tag: {tag_error}")
                                generated_image_tag = None
                            
                            print(f"SnapHook: Generated image tag: {generated_image_tag}")
                            
                            if generated_image_tag:
                                # Check if image exists in registry
                                image_exists = snaphook_instance._check_image_exists_multi_registry(
                                    cache_registry, cache_repo, snaphook_instance.cluster_name, namespace, app_name, 
                                    orig_image_short_digest, pod_template_hash
                                )
                                
                                if image_exists:
                                    should_patch_image = True
                                    # Patch all container images
                                    for i, container in enumerate(containers):
                                        patches.append({
                                            "op": "replace",
                                            "path": f"/spec/containers/{i}/image",
                                            "value": generated_image_tag
                                        })
                                    
                                    # Add mutation label
                                    patches.append({
                                        "op": "replace",
                                        "path": "/metadata/labels/snap.weaversoft.io~1mutated",
                                        "value": "true"
                                    })
                                    
                                    print(f"SnapHook: Patching pod {pod_name} with image {generated_image_tag}")
                                else:
                                    print(f"SnapHook: Image {generated_image_tag} not found in registry, skipping patch")
                            else:
                                print(f"SnapHook: Could not generate image tag for pod {pod_name}")
                        else:
                            print(f"SnapHook: No containers found in pod {pod_name}")
                            
                    except Exception as e:
                        print(f"SnapHook: Error processing pod: {e}")
                        # Continue without patching on error
                    
                    # Create response
                    response = {
                        "apiVersion": "admission.k8s.io/v1",
                        "kind": "AdmissionReview",
                        "response": {
                            "uid": admission_review.get("uid"),
                            "allowed": True,
                            "patch": base64.b64encode(json.dumps(patches).encode()).decode() if patches else None,
                            "patchType": "JSONPatch" if patches else None
                        }
                    }
                    print(f"SnapHook: Response - patched: {len(patches) > 0}")
                    
                    # Send response
                    self._send_json_response(200, response)
                    logger.info(f"SnapHook: Webhook response sent for pod {pod_name}")
                    
                except Exception as e:
                    logger.error(f"SnapHook: Webhook error: {e}")
                    
                    # Return error response
                    error_response = {
                        "apiVersion": "admission.k8s.io/v1",
                        "kind": "AdmissionReview",
                        "response": {
                            "uid": request_data.get("request", {}).get("uid") if 'request_data' in locals() else None,
                            "allowed": False,
                            "status": {
                                "message": f"SnapHook webhook error: {str(e)}"
                            }
                        }
                    }
                    
                    self._send_json_response(500, error_response)
            
            def _send_json_response(self, status_code, data):
                """Send JSON response."""
                response_json = json.dumps(data)
                self.send_response(status_code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(response_json)))
                self.end_headers()
                self.wfile.write(response_json.encode('utf-8'))
            
            def _send_error_response(self, status_code, message):
                """Send error response."""
                self.send_response(status_code)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(message.encode('utf-8'))
            
            def log_message(self, format, *args):
                """Override to use our logger."""
                logger.info(f"SnapHook HTTPS Server: {format % args}")
        
        return WebhookHandler
    
    def _start_https_server(self):
        """Start HTTPS server in a separate thread."""
        try:
            # Create SSL context
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            
            # Load certificate and key
            with tempfile.NamedTemporaryFile(mode='w', suffix='.crt', delete=False) as f:
                f.write(self.cert_data["cert_data"])
                cert_file = f.name
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.key', delete=False) as f:
                f.write(self.cert_data["key_data"])
                key_file = f.name
            
            try:
                ssl_context.load_cert_chain(cert_file, key_file)
                
                # Create HTTPS server
                handler = self._create_webhook_handler()
                self.https_server = HTTPServer(('0.0.0.0', 8443), handler)
                self.https_server.socket = ssl_context.wrap_socket(self.https_server.socket, server_side=True)
                
                logger.info("SnapHook: Starting HTTPS server on port 8443")
                self.is_running = True
                self.https_server.serve_forever()
                
            finally:
                # Clean up temporary files
                os.unlink(cert_file)
                os.unlink(key_file)
                
        except Exception as e:
            logger.error(f"SnapHook: Failed to start HTTPS server: {e}")
            self.is_running = False
    
    def start(self) -> bool:
        """
        Start SnapHook - create webhook configuration and start HTTPS listener.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if shared_https_server is None:
                logger.error("SnapHook: Shared HTTPS server not available")
                return False
            
            logger.info(f"SnapHook: Starting SnapHook '{self.name}' for cluster {self.cluster_name}")
            
            # Step 1: Ensure shared HTTPS server is running
            if not shared_https_server.is_running:
                if not shared_https_server.start_shared_server():
                    logger.error("SnapHook: Failed to start shared HTTPS server")
                    return False
            
            # Step 2: Get shared certificate data
            self.cert_data = shared_https_server.get_cert_data()
            # CA bundle needs to be base64-encoded for Kubernetes
            import base64
            self.ca_bundle = base64.b64encode(shared_https_server.get_ca_bundle().encode('utf-8')).decode('utf-8')
            
            # Step 3: Create MutatingWebhookConfiguration with unique name
            webhook_config = self._create_mutating_webhook_configuration()
            webhook_name = f"snaphook-{self.name}-{self.cluster_name}"
            
            # Step 4: Deploy webhook configuration to Kubernetes
            admission_v1 = client.AdmissionregistrationV1Api(self.kube_client)
            
            # First, try to delete any existing webhook configuration with the same name
            try:
                admission_v1.delete_mutating_webhook_configuration(name=webhook_name)
                logger.info(f"SnapHook: Deleted existing webhook configuration '{webhook_name}'")
                # Wait a moment for the deletion to complete
                import time
                time.sleep(1)
            except ApiException as e:
                if e.status != 404:
                    logger.warning(f"SnapHook: Error deleting existing webhook: {e}")
                # Continue with creation even if deletion fails
            
            # Now create the new webhook configuration
            try:
                logger.info(f"SnapHook: Creating webhook configuration '{webhook_name}'...")
                admission_v1.create_mutating_webhook_configuration(body=webhook_config)
                logger.info("SnapHook: Webhook configuration created successfully")
            except ApiException as e:
                if e.status == 409:  # Conflict - webhook already exists
                    logger.info("SnapHook: Webhook already exists, updating...")
                    # Get existing config and update it
                    existing_config = admission_v1.read_mutating_webhook_configuration(
                        name=webhook_name
                    )
                    # Update the existing config with new data while preserving resourceVersion
                    existing_config.webhooks = webhook_config.webhooks
                    existing_config.metadata.labels = webhook_config.metadata.labels
                    # Update the CA bundle and URL in the webhook
                    if existing_config.webhooks:
                        existing_config.webhooks[0].client_config.ca_bundle = webhook_config.webhooks[0].client_config.ca_bundle
                        existing_config.webhooks[0].client_config.url = webhook_config.webhooks[0].client_config.url
                    
                    admission_v1.replace_mutating_webhook_configuration(
                        name=webhook_name,
                        body=existing_config
                    )
                    logger.info("SnapHook: Webhook configuration updated successfully")
                else:
                    logger.error(f"SnapHook: Failed to create/update webhook configuration: {e}")
                    raise
            
            # Step 5: Register this hook with the shared server
            shared_https_server.register_hook_handler(self.name, self._create_webhook_handler())
            
            self.is_running = True
            logger.info(f"SnapHook: Successfully started '{self.name}' for cluster {self.cluster_name}")
            logger.info(f"SnapHook: Webhook URL: {self.webhook_url}")
            logger.info(f"SnapHook: Using shared HTTPS server on port 8443")
            return True
                
        except Exception as e:
            logger.error(f"SnapHook: Failed to start: {e}")
            import traceback
            logger.error(f"SnapHook: Traceback: {traceback.format_exc()}")
            return False
    
    def _extract_app_name_from_pod(self, pod_name: str, labels: dict) -> str:
        """Extract app name from pod metadata."""
        from flows.helpers import extract_app_name_from_pod
        app = extract_app_name_from_pod(pod_name, labels)
        # Use "unknown" as fallback for webhook (instead of "unknown-app")
        if app == "unknown-app":
            app = "unknown"
        return app
    
    def _extract_digest_from_pod(self, pod: dict) -> str:
        """Extract digest from pod using skopeo if needed."""
        import asyncio
        from flows.helpers import extract_digest
        
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(extract_digest(pod))
        finally:
            loop.close()
    
    def _get_snap_config_from_cluster_cache_api(self, cluster_name: str) -> dict:
        """Get Snap configuration from cluster cache API (synchronous wrapper)."""
        import asyncio
        from flows.helpers import get_snap_config_from_cluster_cache_api
        
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(get_snap_config_from_cluster_cache_api(cluster_name))
        finally:
            loop.close()
    
    def _generate_image_tag(self, registry: str, repo: str, cluster: str, namespace: str, 
                           app: str, origImageShortDigest: str, PodTemplateHash: str) -> str:
        """Generate image tag using SnapApi logic."""
        from classes.imagetag import generate_image_tag
        return generate_image_tag(
            registry=registry,
            repo=repo,
            cluster=cluster,
            namespace=namespace,
            app=app,
            origImageShortDigest=origImageShortDigest,
            PodTemplateHash=PodTemplateHash
        )
    
    def _check_image_exists_multi_registry(self, registry: str, repo: str, cluster: str, 
                                          namespace: str, app: str, orig_digest: str, 
                                          pod_hash: str) -> bool:
        """Check if image exists in registry (synchronous wrapper)."""
        import asyncio
        from flows.helpers import check_image_exists_multi_registry
        
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(check_image_exists_multi_registry(
                registry, repo, cluster, namespace, app, orig_digest, pod_hash
            ))
        finally:
            loop.close()
    
    def stop(self) -> bool:
        """
        Stop SnapHook - unregister from shared server and delete webhook configuration.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if shared_https_server is None:
                logger.error("SnapHook: Shared HTTPS server not available")
                return False
            
            logger.info(f"SnapHook: Stopping SnapHook '{self.name}' for cluster {self.cluster_name}")
            
            # Unregister from shared server
            shared_https_server.unregister_hook_handler(self.name)
            self.is_running = False
            logger.info("SnapHook: Unregistered from shared HTTPS server")
            
            # Delete webhook configuration
            if self.kube_client:
                admission_v1 = client.AdmissionregistrationV1Api(self.kube_client)
                webhook_name = f"snaphook-{self.name}-{self.cluster_name}"
                try:
                    admission_v1.delete_mutating_webhook_configuration(name=webhook_name)
                    logger.info(f"SnapHook: Webhook configuration '{webhook_name}' deleted")
                except ApiException as e:
                    if e.status == 404:
                        logger.info("SnapHook: Webhook configuration not found, already cleaned up")
                    else:
                        raise
            
            logger.info(f"SnapHook: Successfully stopped '{self.name}' for cluster {self.cluster_name}")
            return True
            
        except Exception as e:
            logger.error(f"SnapHook: Failed to stop: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of SnapHook.
        
        Returns:
            Dict containing status information
        """
        return {
            "cluster_name": self.cluster_name,
            "namespace": self.namespace,
            "webhook_url": self.webhook_url,
            "is_running": self.is_running,
            "certificate_generated": self.cert_data is not None,
            "certificate_expiry_days": self.cert_expiry_days,
            "https_server_port": 8443 if self.is_running else None
        }
