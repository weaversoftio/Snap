import os
import json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from classes.clusterconfig import ClusterConfig, ClusterConfigDetails

def detect_service_account_token():
    """
    In-cluster authentication detection disabled.
    SnapAPI now always uses token-based authentication from cluster configuration files.
    """
    print("In-cluster authentication detection disabled - using token-based authentication only")
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
    In-cluster authentication auto-creation disabled.
    SnapAPI now requires explicit cluster configuration files with token-based authentication.
    """
    print("In-cluster authentication auto-creation disabled - using explicit cluster configuration files only")
    return

def snap_init():
    try:
        # Ensure the required directories exist before any operations
        os.makedirs("config/security", exist_ok=True)
        os.makedirs("config/clusters", exist_ok=True)
        os.makedirs("config/registry", exist_ok=True)
        os.makedirs("config/clusterCache", exist_ok=True)
        os.makedirs("config/watcher", exist_ok=True)
        os.makedirs("config/hooks", exist_ok=True)
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
