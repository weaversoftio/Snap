// Documentation data structure for offline use in SnapUI
import { additionalDocumentationSections } from './additionalDocumentationSections';

export const documentationData = {
  sections: [
    {
      id: 'getting-started',
      title: 'Getting Started',
      icon: '🚀',
      pages: [
        {
          id: 'quick-start',
          title: 'Quick Start Guide',
          content: `# Quick Start Guide

Get SNAP up and running in minutes! This guide will walk you through the essential steps to create your first checkpoint.

## Prerequisites

- SNAP installed and running
- Access to an Openshift/Kubernetes cluster
- Container registry credentials

## Step 1: Access SNAP

1. **Open your browser** to the SnapUI interface
2. **Login** with your credentials
3. **Change your password** (recommended)

## Step 2: Configure Registry

1. **Navigate** to **Registry** in the sidebar
2. **Click** "Add New Registry"
3. **Fill in details**:
   - Registry Name: nexus-registry
   - Registry URL: https://your-registry.com
   - Username: your-username
   - Password: your-password
4. **Test connection** and save

## Step 3: Set Up RBAC (Required)

\`\`\`bash
# Set up RBAC permissions for SnapAPI
cd SnapApi
./setup-snapapi-rbac.sh
\`\`\`

This creates the necessary service account and permissions for SnapAPI operations.

## Step 4: Add Cluster

1. **Navigate** to **Clusters** (main page)
2. **Click** "Add Cluster" in the cluster selector
3. **Configure cluster**:
   - Cluster Name: production-cluster
   - API Server URL: https://your-openshift-api:6443
   - Authentication: Enter token
   - Registry: Select your configured registry
4. **Save configuration**

## Step 5: Test Checkpointing

### Deploy Test Application
\`\`\`bash
# Deploy a simple test pod
kubectl run test-app --image=nginx:latest --port=80
\`\`\`

### Create Checkpoint via UI
1. **Navigate** to **Checkpoints**
2. **Click** "Create Checkpoint"
3. **Fill in details**:
   - Pod Name: test-app
   - Namespace: default
   - Container Name: test-app
4. **Click** "Create Checkpoint"

## Success!

Congratulations! You've successfully:
- ✅ Installed and configured SNAP
- ✅ Set up RBAC permissions
- ✅ Connected to your Openshift cluster
- ✅ Created your first checkpoint

You're now ready to use SNAP for production container checkpointing and migration workflows!`
        },
        {
          id: 'installation',
          title: 'Installation Guide',
          content: `# Installation Guide

This guide will walk you through installing and setting up SNAP on your system.

## Prerequisites

Before installing SNAP, ensure you have the following:

### System Requirements
- **Operating System**: Linux (RHEL, CentOS, Ubuntu, or similar)
- **Memory**: Minimum 4GB RAM, Recommended 8GB+
- **Storage**: Minimum 20GB free disk space
- **Network**: Internet access for downloading images

### Required Software
- **Docker**: Version 20.10 or later
- **Docker Compose**: Version 2.0 or later
- **kubectl**: For cluster management
- **Access to Openshift/Kubernetes cluster**

### Cluster Requirements
- **Openshift**: Version 4.8+ or Kubernetes 1.21+
- **Container Runtime**: CRI-O or containerd
- **Registry Access**: Container registry credentials (Nexus, Harbor, etc.)

## Installation Methods

### Method 1: Docker Compose (Recommended)

#### Step 1: Download SNAP
\`\`\`bash
# Clone the repository
git clone https://github.com/weaversoftio/Snap.git
cd Snap

# Or download the release
wget https://github.com/weaversoftio/Snap/releases/latest/download/snap-release.tar.gz
tar -xzf snap-release.tar.gz
cd Snap
\`\`\`

#### Step 2: Start SNAP Services
\`\`\`bash
# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps
\`\`\`

#### Step 3: Verify Installation
\`\`\`bash
# Check API health
curl http://localhost:8000/health

# Check UI accessibility
curl http://localhost:3000

# View logs
docker-compose logs -f
\`\`\`

## Post-Installation Configuration

### 1. Access Web Interface
- Open browser to \`http://localhost:3000\` (Docker Compose)
- Login with default credentials: \`admin/admin\`

### 2. Initial Setup
1. **Change default password**
2. **Configure registry connection**
3. **Set up RBAC permissions** (see RBAC Setup section)
4. **Add your first cluster**
5. **Deploy cluster monitor DaemonSet**

### 3. RBAC Setup (Required)
\`\`\`bash
# Set up RBAC permissions for SnapAPI
cd SnapApi
./setup-snapapi-rbac.sh
\`\`\`

This script creates:
- Service account (\`snapapi-serviceaccount\`)
- Cluster role with required permissions
- Cluster role binding
- Permanent service account token

**Required Permissions:**
- Nodes and nodes/proxy access for checkpoint operations
- Pods, pods/log, pods/exec for debug operations
- Webhook management permissions
- Privileged SCC usage for OpenShift

### 4. Deploy Cluster Monitor DaemonSet
\`\`\`bash
# Deploy to your Openshift/Kubernetes cluster
kubectl apply -f SnapApi/snap-cluster-monitor-daemonset.yaml

# Verify deployment
kubectl get daemonset -n snap
\`\`\`

## Verification Steps

### 1. Service Health Checks
\`\`\`bash
# Check SnapAPI health
curl -f http://localhost:8000/health

# Check SnapUI accessibility
curl -f http://localhost:3000

# Check API documentation
curl -f http://localhost:8000/docs
\`\`\`

### 2. Cluster Connectivity
Test cluster connection via the SnapUI interface:
1. Navigate to the main cluster page
2. Add your cluster configuration
3. Verify connection status

### 3. Registry Connectivity
Test registry connection:
1. Navigate to Registry in SnapUI
2. Add registry configuration
3. Test connection

## Troubleshooting Installation

### Common Issues

#### Services Won't Start
\`\`\`bash
# Check Docker status
docker --version
docker-compose --version

# Check port availability
netstat -tulpn | grep :8000
netstat -tulpn | grep :3000

# View detailed logs
docker-compose logs snapapi
docker-compose logs snapui
\`\`\`

#### Permission Issues
\`\`\`bash
# Fix Docker permissions
sudo usermod -aG docker $USER
newgrp docker

# Check volume permissions
ls -la snapapi-checkpoints/
\`\`\`

#### Network Connectivity
\`\`\`bash
# Test internal network
docker-compose exec snapapi ping snapui
docker-compose exec snapui ping snapapi

# Check DNS resolution
docker-compose exec snapapi nslookup snapui
\`\`\`

## Next Steps

After successful installation:

1. **Follow the Quick Start Guide**
2. **Configure your first cluster**
3. **Set up registry integration**
4. **Deploy SnapWatcher operator**
5. **Create your first checkpoint**

## Support

If you encounter issues during installation:

- Check the Troubleshooting Guide
- Review the GitHub Issues
- Contact support at support@weaversoft.io`
        },
        {
          id: 'configuration',
          title: 'Configuration Guide',
          content: `# Configuration Guide

This guide covers system and cluster configuration for SNAP.

## System Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| \`SNAP_ORIGINS\` | Allowed CORS origins | \`http://localhost:3000,*\` |
| \`SNAP_API_URL\` | API base URL | \`http://localhost:8000\` |
| \`WATCHER_CLUSTER_NAME\` | Default cluster name | \`crc\` |
| \`KUBE_VERIFY_SSL\` | SSL verification | \`false\` |
| \`FLASK_ENV\` | Environment mode | \`development\` |

### Docker Compose Configuration
\`\`\`yaml
# docker-compose.yaml
version: '3.8'
services:
  snapapi:
    image: snapapi:latest
    ports:
      - "8000:8000"
      - "8443:8443"
    environment:
      - SNAP_ORIGINS=http://localhost:3000,*
      - SNAP_API_URL=http://localhost:8000
      - WATCHER_CLUSTER_NAME=your-cluster
      - KUBE_VERIFY_SSL=false
    volumes:
      - snapapi-checkpoints:/app/checkpoints
    networks:
      - snap-network

  snapui:
    image: snapui:latest
    ports:
      - "3000:3000"
    environment:
      - API_URL=http://localhost:8000
      - WS_URL=ws://localhost:8000
    networks:
      - snap-network

volumes:
  snapapi-checkpoints:

networks:
  snap-network:
    driver: bridge
\`\`\`

## Cluster Configuration

### Adding a Cluster

1. **Navigate** to the main cluster page in SnapUI
2. **Click** "Add Cluster" in the cluster selector dropdown
3. **Fill in cluster details**:
   - **Cluster Name**: Unique identifier for your cluster
   - **API Server URL**: Kubernetes API server endpoint
   - **Token**: Service account token for authentication
   - **Registry**: Optional registry for checkpoint images
   - **SSH Key**: Optional SSH key for cluster access

### Cluster Authentication

#### Token-based Authentication
\`\`\`bash
# Generate service account token
kubectl create serviceaccount snapapi-serviceaccount -n snap
kubectl create clusterrolebinding snapapi-clusterrolebinding \\
  --clusterrole=cluster-admin \\
  --serviceaccount=snap:snapapi-serviceaccount

# Get token
kubectl get secret -n snap -o jsonpath='{.items[?(@.metadata.annotations.kubernetes\\.io/service-account\\.name=="snapapi-serviceaccount")].data.token}' | base64 -d
\`\`\`

#### Kubeconfig Authentication
Upload your kubeconfig file or paste the contents directly.

### Registry Configuration

#### Adding a Registry

1. **Navigate** to **Registry** in SnapUI
2. **Click** "Add New Registry"
3. **Configure registry**:
   - **Registry Name**: Unique identifier
   - **Registry URL**: Registry endpoint
   - **Username**: Registry username
   - **Password**: Registry password
   - **Repository**: Default repository name

#### Supported Registries
- **Nexus Repository Manager**
- **Harbor**
- **Docker Hub**
- **Amazon ECR**
- **Azure Container Registry**
- **Google Container Registry**

## RBAC Configuration

### Automated RBAC Setup

\`\`\`bash
# Run the automated RBAC setup script
cd SnapApi
./setup-snapapi-rbac.sh
\`\`\`

### Manual RBAC Setup

#### Service Account
\`\`\`yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: snapapi-serviceaccount
  namespace: snap
automountServiceAccountToken: true
\`\`\`

#### Cluster Role
\`\`\`yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: snapapi-clusterrole
rules:
  - apiGroups: [""]
    resources: ["nodes", "nodes/proxy", "pods", "pods/log", "pods/exec", "namespaces"]
    verbs: ["get", "list", "watch", "create", "delete"]
  - apiGroups: ["apps"]
    resources: ["replicasets"]
    verbs: ["get", "list"]
  - apiGroups: ["security.openshift.io"]
    resources: ["securitycontextconstraints"]
    verbs: ["use"]
    resourceNames: ["privileged"]
  - apiGroups: ["admissionregistration.k8s.io"]
    resources: ["mutatingwebhookconfigurations", "validatingwebhookconfigurations"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
\`\`\`

#### Cluster Role Binding
\`\`\`yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: snapapi-clusterrolebinding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: snapapi-clusterrole
subjects:
- kind: ServiceAccount
  name: snapapi-serviceaccount
  namespace: snap
\`\`\`

## Security Configuration

### SSL/TLS Configuration
- **API Endpoints**: HTTPS for all API calls
- **Web Interface**: SSL certificates
- **Registry Communication**: Secure registry connections
- **Cluster Communication**: Encrypted cluster API calls

### Firewall Rules
\`\`\`
# Allow SNAP API access
8000/tcp - SnapAPI HTTP
8443/tcp - SnapAPI HTTPS/Webhooks
3000/tcp - SnapUI (if external access needed)

# Block unnecessary ports
# Only allow required cluster ports
\`\`\`

## Monitoring Configuration

### Log Configuration
- **Log Level**: Set appropriate log levels for production
- **Log Rotation**: Configure log rotation to prevent disk space issues
- **Log Aggregation**: Set up centralized logging if needed

### Health Checks
- **API Health**: Monitor SnapAPI health endpoint
- **Cluster Health**: Monitor cluster connectivity
- **Registry Health**: Monitor registry connectivity

## Performance Tuning

### Resource Limits
\`\`\`yaml
resources:
  limits:
    memory: "2Gi"
    cpu: "1000m"
  requests:
    memory: "1Gi"
    cpu: "500m"
\`\`\`

### Checkpoint Storage
- **Storage Class**: Use appropriate storage class for checkpoint storage
- **Volume Size**: Allocate sufficient storage for checkpoints
- **Cleanup Policy**: Configure automatic cleanup of old checkpoints

## Backup Configuration

### Checkpoint Backup
- **Backup Schedule**: Set up regular backup schedule
- **Backup Location**: Configure backup storage location
- **Retention Policy**: Define backup retention policy

### Configuration Backup
- **Configuration Export**: Export configuration regularly
- **Version Control**: Use version control for configuration changes
- **Disaster Recovery**: Plan for disaster recovery scenarios

## Troubleshooting Configuration

### Common Configuration Issues

#### Cluster Connection Issues
- Verify API server URL
- Check token validity
- Ensure network connectivity
- Verify RBAC permissions

#### Registry Connection Issues
- Verify registry URL and credentials
- Check network connectivity
- Ensure registry permissions
- Verify repository access

#### RBAC Permission Issues
- Run RBAC setup script
- Verify service account permissions
- Check cluster role binding
- Ensure token is valid

### Configuration Validation

#### Cluster Validation
\`\`\`bash
# Test cluster connection
kubectl cluster-info

# Verify permissions
kubectl auth can-i get pods --as=system:serviceaccount:snap:snapapi-serviceaccount
\`\`\`

#### Registry Validation
\`\`\`bash
# Test registry connection
docker login your-registry.com

# Test image push/pull
docker pull hello-world
docker tag hello-world your-registry.com/test:latest
docker push your-registry.com/test:latest
\`\`\`

## Best Practices

1. **Regular Audits**: Periodically review and audit configurations
2. **Documentation**: Keep configuration documentation up to date
3. **Testing**: Test configurations in non-production environments first
4. **Monitoring**: Monitor configuration changes and their impact
5. **Backup**: Regular backup of configurations and data`
        }
      ]
    },
    ...additionalDocumentationSections
  ]
};
