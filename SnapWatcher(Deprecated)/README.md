# SnapWatcher

**Kubernetes Operator for Automatic Pod Checkpointing**

*"SNAP it, Save it, Start again."*

## Overview

SnapWatcher is a Kubernetes operator that automatically monitors and checkpoints pods based on specific labels. Built with the Kopf (Kubernetes Operator Pythonic Framework), SnapWatcher provides seamless integration with the SNAP ecosystem to enable automatic container checkpointing for disaster recovery, migration, and state preservation.

## Features

- 🔍 **Automatic Pod Monitoring**: Watches for pods with specific labels across all namespaces
- ⚡ **Smart Checkpointing**: Triggers checkpoints only when pods are ready and running
- 🔄 **Duplicate Prevention**: Prevents multiple checkpoints of the same pod using UID tracking
- 🏗️ **Deployment Resolution**: Automatically resolves deployment ownership through ReplicaSets
- 🔐 **Security First**: Runs as non-root user with comprehensive security contexts
- 📊 **Resource Efficient**: Configurable resource limits and requests
- 🚀 **Easy Deployment**: Helm chart included for streamlined installation

## Architecture

SnapWatcher operates as a Kubernetes operator that:

1. **Monitors Pod Events**: Listens for pod events with labels:
   - `snap.weaversoft.io/snap: true`
   - `snap.weaversoft.io/mutated: false`

2. **Validates Pod State**: Ensures pods are:
   - In "Running" phase
   - Reporting Ready=True condition
   - Have at least one container started and running
   - Not being deleted or terminated

3. **Resolves Ownership**: Traces pod ownership back to Deployments through ReplicaSets

4. **Triggers Checkpointing**: Sends checkpoint requests to SnapHook API (when configured)

## Prerequisites

- Kubernetes cluster (v1.20+)
- Helm 3.x (for Helm installation)
- Container runtime with checkpointing support
- RBAC permissions for cluster-wide pod monitoring

## Installation

### Using Helm (Recommended)

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd snap/SnapWatcher
   ```

2. **Install using Helm**:
   ```bash
   helm install snapwatcher ./charts/snapwatcher -n snap --create-namespace
   ```

3. **Verify installation**:
   ```bash
   kubectl get pods -n snap
   kubectl logs -n snap deployment/snapwatcher
   ```

### Using Make

1. **Build and deploy**:
   ```bash
   make install
   ```

2. **Clean up**:
   ```bash
   make clean
   ```

### Manual Installation

1. **Apply RBAC configuration**:
   ```bash
   kubectl apply -f manifests/rbac.yaml
   ```

2. **Deploy the operator**:
   ```bash
   kubectl apply -f manifests/deployment.yaml
   ```

## Configuration

### Helm Values

Key configuration options in `values.yaml`:

```yaml
# Image configuration
image:
  repository: 192.168.33.204:8082/snapwatcher
  tag: "latest"
  pullPolicy: Always

# Resource limits
resources:
  limits:
    cpu: 200m
    memory: 256Mi
  requests:
    cpu: 50m
    memory: 64Mi

# SnapWatcher specific configuration
snapwatcher:
  operator:
    logLevel: "INFO"
    allNamespaces: true
    standalone: true
  
  checkpoint:
    snapBackApiUrl: "http://snap-back-api"
    kubeApiAddress: "https://kubernetes.default.svc"
    requestTimeout: 5
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `SNAP_BACK_API_URL` | SnapHook API endpoint for checkpoints | `http://snap-back-api` |
| `KUBE_API_ADDRESS` | Kubernetes API server address | `https://kubernetes.default.svc` |

## Usage

### Labeling Pods for Checkpointing

To enable automatic checkpointing for a pod, add the required labels:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: my-app
  labels:
    snap.weaversoft.io/snap: "true"
    snap.weaversoft.io/mutated: "false"
spec:
  containers:
  - name: app
    image: my-app:latest
```

### Deployment Example

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: checkpointed-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: checkpointed-app
  template:
    metadata:
      labels:
        app: checkpointed-app
        snap.weaversoft.io/snap: "true"
        snap.weaversoft.io/mutated: "false"
    spec:
      containers:
      - name: app
        image: nginx:latest
        ports:
        - containerPort: 80
```

### Monitoring

Check SnapWatcher logs to monitor checkpointing activity:

```bash
kubectl logs -n snap deployment/snapwatcher -f
```

Expected log output when a pod is checkpointed:
```
Now we should checkpoint
  Event:      ADDED
  Namespace:  default
  Deployment: my-app
  Pod:        my-app-7d4b8c8f9-xyz12
  Container:  app
  Node:       worker-node-1
```

## Development

### Local Development Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run locally** (requires kubeconfig):
   ```bash
   kopf run --standalone --all-namespaces operator.py
   ```

### Building Container Image

```bash
# Using Podman
podman build -t snapwatcher:latest .

# Using Docker
docker build -t snapwatcher:latest .
```

### Testing

1. **Create test pod**:
   ```bash
   kubectl apply -f manifests/app-deployment-test.yaml
   ```

2. **Monitor logs**:
   ```bash
   kubectl logs -n snap deployment/snapwatcher -f
   ```

## Dependencies

- **kopf** (>=1.37.2): Kubernetes Operator Pythonic Framework
- **kubernetes** (>=26.1.0): Official Kubernetes Python client
- **requests** (>=2.31.0): HTTP library for API calls
- **pydantic** (>=2.0.0): Data validation and settings management

## Security

SnapWatcher implements security best practices:

- **Non-root execution**: Runs as user ID 1001
- **Read-only root filesystem**: Prevents runtime modifications
- **Security contexts**: Comprehensive seccomp and security profiles
- **Minimal privileges**: RBAC with least-privilege access
- **No privilege escalation**: Prevents container breakout

## Troubleshooting

### Common Issues

1. **Operator not starting**:
   ```bash
   # Check RBAC permissions
   kubectl auth can-i get pods --as=system:serviceaccount:snap:snapwatcher
   
   # Check logs
   kubectl logs -n snap deployment/snapwatcher
   ```

2. **Pods not being checkpointed**:
   - Verify pod labels are correct
   - Ensure pod is in "Running" state with Ready=True
   - Check if pod has been checkpointed before (UID tracking)

3. **Permission denied errors**:
   ```bash
   # Verify service account and RBAC
   kubectl get serviceaccount -n snap
   kubectl get clusterrole snapwatcher
   kubectl get clusterrolebinding snapwatcher
   ```

### Debug Mode

Enable debug logging by setting environment variable:

```yaml
env:
- name: LOG_LEVEL
  value: "DEBUG"
```

## Integration with SNAP Ecosystem

SnapWatcher is part of the larger SNAP ecosystem:

- **SnapApi**: REST API for checkpoint management
- **SnapHook**: Webhook service for checkpoint execution
- **SnapUi**: Web interface for monitoring and management

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is part of the SNAP operator suite developed by WeaverSoft.

## Support

For support and questions:
- Email: support@weaversoft.io
- Repository: https://github.com/weaversoft/snap

---

**SnapWatcher** - Automatic Kubernetes Pod Checkpointing Made Simple
