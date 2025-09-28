# Installation Guide

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
```bash
# Clone the repository
git clone https://github.com/weaversoftio/Snap.git
cd Snap

# Or download the release
wget https://github.com/weaversoftio/Snap/releases/latest/download/snap-release.tar.gz
tar -xzf snap-release.tar.gz
cd Snap
```

#### Step 2: Configure Environment
```bash
# Copy environment template
cp docker-compose.yaml.example docker-compose.yaml

# Edit configuration
nano docker-compose.yaml
```

#### Step 3: Start SNAP Services
```bash
# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps
```

#### Step 4: Verify Installation
```bash
# Check API health
curl http://localhost:8000/health

# Check UI accessibility
curl http://localhost:3000

# View logs
docker-compose logs -f
```

### Method 2: Kubernetes Deployment

#### Step 1: Prepare Kubernetes Cluster
```bash
# Create namespace
kubectl create namespace snap

# Apply RBAC permissions
kubectl apply -f k8s/rbac.yaml
```

#### Step 2: Deploy SNAP Components
```bash
# Deploy SnapAPI
kubectl apply -f k8s/snapapi-deployment.yaml

# Deploy SnapUI
kubectl apply -f k8s/snapui-deployment.yaml

# Deploy services
kubectl apply -f k8s/services.yaml
```

#### Step 3: Configure Ingress
```bash
# Apply ingress configuration
kubectl apply -f k8s/ingress.yaml
```

### Method 3: Helm Chart

#### Step 1: Add Helm Repository
```bash
# Add SNAP Helm repository
helm repo add snap https://weaversoftio.github.io/Snap/charts
helm repo update
```

#### Step 2: Install SNAP
```bash
# Install with default values
helm install snap snap/snap

# Or install with custom values
helm install snap snap/snap -f values.yaml
```

## Post-Installation Configuration

### 1. Access Web Interface
- Open browser to `http://localhost:3000` (Docker Compose)
- Or use your Kubernetes ingress URL
- Login with default credentials: `admin/admin`

### 2. Initial Setup
1. **Change default password**
2. **Configure registry connection**
3. **Add your first cluster**
4. **Deploy cluster monitor DaemonSet**

### 3. Deploy Cluster Monitor DaemonSet
```bash
# Deploy to your Openshift/Kubernetes cluster
kubectl apply -f SnapApi/snap-cluster-monitor-daemonset.yaml

# Verify deployment
kubectl get daemonset -n snap
```

## Configuration Files

### Docker Compose Configuration
```yaml
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
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SNAP_ORIGINS` | Allowed CORS origins | `http://localhost:3000,*` |
| `SNAP_API_URL` | API base URL | `http://localhost:8000` |
| `WATCHER_CLUSTER_NAME` | Default cluster name | `crc` |
| `KUBE_VERIFY_SSL` | SSL verification | `false` |
| `FLASK_ENV` | Environment mode | `development` |

## Verification Steps

### 1. Service Health Checks
```bash
# Check SnapAPI health
curl -f http://localhost:8000/health

# Check SnapUI accessibility
curl -f http://localhost:3000

# Check API documentation
curl -f http://localhost:8000/docs
```

### 2. Cluster Connectivity
```bash
# Test cluster connection via API
curl -X POST http://localhost:8000/cluster/verify_checkpointing \
  -H "Content-Type: application/json" \
  -d '{"cluster_name": "your-cluster"}'
```

### 3. Registry Connectivity
```bash
# Test registry connection
curl -X POST http://localhost:8000/registry/login \
  -H "Content-Type: application/json" \
  -d '{"registry_config_name": "your-registry"}'
```

## Troubleshooting Installation

### Common Issues

#### Services Won't Start
```bash
# Check Docker status
docker --version
docker-compose --version

# Check port availability
netstat -tulpn | grep :8000
netstat -tulpn | grep :3000

# View detailed logs
docker-compose logs snapapi
docker-compose logs snapui
```

#### Permission Issues
```bash
# Fix Docker permissions
sudo usermod -aG docker $USER
newgrp docker

# Check volume permissions
ls -la snapapi-checkpoints/
```

#### Network Connectivity
```bash
# Test internal network
docker-compose exec snapapi ping snapui
docker-compose exec snapui ping snapapi

# Check DNS resolution
docker-compose exec snapapi nslookup snapui
```

## Next Steps

After successful installation:

1. **Follow the [Quick Start Guide](quick-start.md)**
2. **Configure your first cluster**
3. **Set up registry integration**
4. **Deploy SnapWatcher operator**
5. **Create your first checkpoint**

## Support

If you encounter issues during installation:

- Check the [Troubleshooting Guide](troubleshooting.md)
- Review the [GitHub Issues](https://github.com/weaversoftio/Snap/issues)
- Contact support at support@weaversoft.io
