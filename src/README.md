# Snap Kubernetes Operator

A simple Kubernetes operator built with Python and the Kopf framework that watches for pods with specific `snap` annotations and logs container information.

## Features

- Watches for pods with `snap/containers` or `snap/info` annotations
- Logs namespace-pod-container information in the format: `namespace-pod_name-container_name`
- Handles multiple containers per pod
- Parses and logs JSON data from `snap/info` annotations
- Supports both OpenShift and standard Kubernetes

## Annotations Supported

The operator watches for pods with these annotations:

### Option 1: Simple containers annotation
```yaml
annotations:
  snap/containers: "ace"
  snap/info: '{"checkpointed":false,"checkpointedTime":""}'
```

### Option 2: Multi-line info annotation
```yaml
annotations:
  snap/info: >
    {"checkpointed":true,
     "checkpointedTime":"2025-07-31T16:00:00Z"}
```

## Architecture

- **Framework**: Kopf (Python Kubernetes Operator Framework)
- **Python Version**: 3.11+
- **Dependencies**: kubernetes, kopf, pyyaml

## Quick Start

### Prerequisites

- Python 3.11+
- Docker
- kubectl configured for your cluster
- Access to a Kubernetes/OpenShift cluster

### Local Development

1. **Install dependencies**:
   ```bash
   cd src
   pip install -r requirements.txt
   ```

2. **Run locally** (requires kubeconfig):
   ```bash
   python operator.py
   ```

### Building and Deploying

1. **Build the Docker image**:
   ```bash
   cd src
   docker build -t snap-operator:latest .
   ```

2. **Deploy to cluster**:
   ```bash
   kubectl apply -f k8s-manifests.yaml
   ```

3. **Verify deployment**:
   ```bash
   kubectl get pods -l app=snap-operator
   kubectl logs -l app=snap-operator
   ```

### Testing

1. **Deploy test pods**:
   ```bash
   kubectl apply -f test-pod.yaml
   ```

2. **Check operator logs**:
   ```bash
   kubectl logs -l app=snap-operator -f
   ```

Expected output:
```
INFO:=== Snap Pod Event: ADDED ===
INFO:Namespace: default
INFO:Pod Name: test-snap-pod
INFO:Containers:
INFO:  default-test-snap-pod-ace-container
INFO:  default-test-snap-pod-sidecar-container
INFO:snap/containers: ace
INFO:snap/info: {'checkpointed': False, 'checkpointedTime': ''}
INFO:==================================================
```

## Configuration

The operator can be configured via environment variables:

- `LOG_LEVEL`: Set logging level (default: INFO)
- `PYTHONUNBUFFERED`: Ensure Python output is not buffered

## RBAC Permissions

The operator requires these permissions:
- **Pods**: get, list, watch
- **Events**: create, patch
- **Pods/Log**: get (for potential future features)

## Monitoring

- Check operator health: `kubectl get pods -l app=snap-operator`
- View logs: `kubectl logs -l app=snap-operator`
- Check events: `kubectl get events --field-selector involvedObject.name=snap-operator`

## Troubleshooting

### Common Issues

1. **Permission denied**: Ensure RBAC is properly configured
2. **Image pull errors**: Build and tag the image locally or push to a registry
3. **Connection refused**: Check if the operator can reach the Kubernetes API

### Debug Mode

To enable debug logging, modify the ConfigMap:
```yaml
data:
  log-level: "DEBUG"
```

## Development

### Adding New Features

1. Modify `operator.py` to add new annotation watchers
2. Update `has_snap_annotations()` function for new annotation types
3. Test with sample pods
4. Update documentation

### Testing Locally

```bash
# Start a local cluster (e.g., minikube, kind)
minikube start

# Apply manifests
kubectl apply -f k8s-manifests.yaml

# Run operator locally
python operator.py
```

## License

This project is provided as-is for educational and development purposes.
