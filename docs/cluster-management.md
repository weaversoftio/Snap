# Cluster Management

This guide covers how to manage Openshift and Kubernetes clusters in SNAP.

## Adding a New Cluster

### Prerequisites
- Valid kubeconfig file or authentication token
- Network access to cluster API server
- Registry configuration (optional but recommended)

### Step-by-Step Process

1. **Navigate to Configuration**
   - Go to **Configuration > Clusters**
   - Click **Add New Cluster**

2. **Basic Configuration**
   ```
   Cluster Name: production-cluster
   API Server URL: https://api.cluster.com:6443
   Authentication Type: kubeconfig
   ```

3. **Authentication Setup**
   - **Kubeconfig**: Upload your kubeconfig file
   - **Token**: Enter authentication token
   - **Service Account**: Use existing service account

4. **Registry Selection**
   - Select configured registry for image storage
   - This enables checkpoint-to-image conversion

5. **Advanced Settings**
   - **Namespace**: Default namespace for operations
   - **SSL Verification**: Enable/disable SSL verification
   - **Timeout**: API request timeout settings

## Cluster Operations

### Enable Checkpointing
```bash
curl -X POST http://localhost:8000/cluster/enable_checkpointing \
  -H "Content-Type: application/json" \
  -d '{
    "cluster_name": "production-cluster",
    "node_names": ["worker-node-1", "worker-node-2"]
  }'
```

### Install runC
```bash
curl -X POST http://localhost:8000/cluster/install_runc \
  -H "Content-Type: application/json" \
  -d '{
    "cluster_name": "production-cluster",
    "runc_version": "1.2.4"
  }'
```

### Verify Checkpointing
```bash
curl -X POST http://localhost:8000/cluster/verify_checkpointing \
  -H "Content-Type: application/json" \
  -d '{"cluster_name": "production-cluster"}'
```

## Cluster Monitoring

### Deploy Cluster Monitor DaemonSet
```bash
kubectl apply -f SnapApi/snap-cluster-monitor-daemonset.yaml
```

### Check Cluster Status
- **Dashboard**: Real-time cluster health
- **Node Status**: Individual node checkpointing capabilities
- **Resource Usage**: CPU, memory, and storage metrics

## Troubleshooting Cluster Issues

### Common Problems
- **Connection Failed**: Check network connectivity and credentials
- **Permission Denied**: Verify RBAC permissions
- **Checkpointing Disabled**: Enable checkpointing on nodes
- **Resource Constraints**: Check node resources

### Diagnostic Commands
```bash
# Check cluster connectivity
kubectl cluster-info

# Verify node status
kubectl get nodes -o wide

# Check DaemonSet status
kubectl get daemonset -n snap

# View cluster events
kubectl get events --all-namespaces
```
