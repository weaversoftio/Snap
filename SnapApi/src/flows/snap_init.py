import os
import json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from classes.clusterconfig import ClusterConfig, ClusterConfigDetails

def detect_service_account_token():
    """
    Detect if running in a Kubernetes pod with a service account token.
    Returns the token content if found, None otherwise.
    """
    token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
    try:
        if os.path.exists(token_path):
            with open(token_path, "r") as f:
                token = f.read().strip()
                if token:
                    print("Service account token detected")
                    return token
    except Exception as e:
        print(f"Error reading service account token: {e}")
    return None

def get_kubernetes_api_url():
    """
    Get the Kubernetes API server URL from environment variables or default.
    """
    # Try to get from environment variables (standard Kubernetes injection)
    kube_host = os.getenv("KUBERNETES_SERVICE_HOST")
    kube_port = os.getenv("KUBERNETES_SERVICE_PORT", "443")
    
    if kube_host:
        api_url = f"https://{kube_host}:{kube_port}"
        print(f"Kubernetes API URL detected: {api_url}")
        return api_url
    
    # Fallback to default cluster DNS name
    default_url = "https://kubernetes.default.svc.cluster.local"
    print(f"Using default Kubernetes API URL: {default_url}")
    return default_url

def auto_create_local_cluster():
    """
    Automatically create/update a local cluster configuration if service account token is present.
    Always refreshes the token on each startup to handle token expiration.
    """
    try:
        local_cluster_path = "config/clusters/local.json"
        
        # Detect service account token
        token = detect_service_account_token()
        if not token:
            print("No service account token found, skipping local cluster auto-creation")
            return
        
        # Get Kubernetes API URL
        api_url = get_kubernetes_api_url()
        
        # Always create/update the local cluster configuration with fresh token
        cluster_config_dict = {
            "cluster_config_details": {
                "kube_api_url": api_url,
                "token": token
            },
            "name": "local"
        }
        
        # Save the configuration (overwrite if exists to refresh token)
        with open(local_cluster_path, "w") as f:
            json.dump(cluster_config_dict, f, indent=4)
        
        if os.path.exists(local_cluster_path):
            print("Local cluster configuration updated successfully with fresh service account token")
        else:
            print("Local cluster configuration created successfully with service account token")
        
    except Exception as e:
        print(f"Failed to auto-create/update local cluster configuration: {e}")

def snap_init():
    try:
        # Ensure the required directories exist before any operations
        os.makedirs("config/security", exist_ok=True)
        os.makedirs("config/clusters", exist_ok=True)
        os.makedirs("config/registry", exist_ok=True)
        os.makedirs("config/clusterCache", exist_ok=True)
        os.makedirs("config/watcher", exist_ok=True)
        os.makedirs("config/security/users", exist_ok=True)
        os.makedirs("config/security/secrets", exist_ok=True)
        
        # Always check for local cluster auto-creation, regardless of initialization status
        auto_create_local_cluster()
        
        # check if config/snap_init_done file exists
        if os.path.exists("config/snap_init_done"):
            print("SNAP is already initialized")
            return

        # Load the RSA keys if they are not existing, generate them
        private_key_path = "config/security/private.pem"
        public_key_path = "config/security/public.pem"

        if not os.path.exists(private_key_path):
            # Generate private key
            print("Generating private key...")
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )

            # Save private key
            with open(private_key_path, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))

            # Save public key
            with open(public_key_path, "wb") as f:
                f.write(private_key.public_key().public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ))

        # Create a user admin with password admin
        print("Creating user admin...")
        with open("config/security/users/admin.json", "w") as f:
            json.dump({"userdetails": {"name": "Super Admin", "role": "admin", "username": "admin", "password": "admin"}, "name": "admin"}, f)

        # Mark initialization as done
        with open("config/snap_init_done", "w") as f:
            f.write("snap_init_done")

        print("SNAP initialization complete.")

    except Exception as e:
        print("Failed to initialize snap, error: ", str(e))

# Run the function
snap_init()
