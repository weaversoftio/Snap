# Quick Start Guide

Get SNAP up and running in minutes! This guide will walk you through the essential steps to create your first checkpoint.

## Prerequisites

- SNAP installed and running (see [Installation Guide](installation.md))
- Access to an Openshift/Kubernetes cluster
- Container registry credentials

## Step 1: Access SNAP

1. **Open your browser** to `http://localhost:3000`
2. **Login** with default credentials:
   - Username: `admin`
   - Password: `admin`
3. **Change your password** (recommended)

## Step 2: Configure Registry

1. **Navigate** to **Configuration > Registry**
2. **Click** "Add New Registry"
3. **Fill in details**:
   ```
   Registry Name: nexus-registry
   Registry URL: https://your-registry.com
   Username: your-username
   Password: your-password
   ```
4. **Test connection** and save

## Step 3: Add Cluster

1. **Navigate** to **Configuration > Clusters**
2. **Click** "Add New Cluster"
3. **Configure cluster**:
   ```
   Cluster Name: production-cluster
   API Server URL: https://your-openshift-api:6443
   Authentication: Upload kubeconfig or enter token
   Registry: Select your configured registry
   ```
4. **Save configuration**

## Step 4: Deploy Cluster Monitor

```bash
# Deploy the cluster monitoring DaemonSet
kubectl apply -f SnapApi/snap-cluster-monitor-daemonset.yaml

# Verify deployment
kubectl get daemonset -n snap
```

## Step 5: Start SnapWatcher

1. **Navigate** to **Operator > Start SnapWatcher**
2. **Select** your cluster
3. **Click** "Start SnapWatcher"
4. **Verify** operator is running

## Step 6: Create SnapHook (Optional)

1. **Navigate** to **SnapHook > Create SnapHook**
2. **Configure**:
   ```
   Name: production-snaphook
   Cluster: Select your cluster
   Namespace: snap
   ```
3. **Create SnapHook**

## Step 7: Test Checkpointing

### Deploy Test Application
```bash
# Deploy a simple test pod
kubectl run test-app --image=nginx:latest --port=80

# Verify pod is running
kubectl get pods test-app
```

### Create Checkpoint via UI
1. **Navigate** to **Checkpoints**
2. **Click** "Create Checkpoint"
3. **Fill in details**:
   ```
   Pod Name: test-app
   Namespace: default
   Container Name: test-app
   Cluster: production-cluster
   ```
4. **Click** "Create Checkpoint"

### Create Checkpoint via API
```bash
curl -X POST "http://localhost:8000/checkpoint/kubelet/checkpoint" \
  -H "Content-Type: application/json" \
  -d '{
    "pod_name": "test-app",
    "namespace": "default",
    "node_name": "worker-node-1",
    "container_name": "test-app",
    "cluster_name": "production-cluster"
  }'
```

## Step 8: Convert to Image

1. **Navigate** to **Checkpoints**
2. **Find** your created checkpoint
3. **Click** "Convert to Image"
4. **Configure** image details:
   ```
   Image Name: test-app-checkpoint
   Tag: latest
   Registry: nexus-registry
   ```
5. **Click** "Create and Push Image"

## Step 9: Verify Results

### Check Checkpoint Status
```bash
# List checkpoints
curl http://localhost:8000/checkpoint/list

# Check checkpoint files
ls -la SnapApi/src/checkpoints/
```

### Verify Image Creation
```bash
# Check registry for new image
docker pull your-registry.com/test-app-checkpoint:latest

# Or check via kubectl
kubectl get images | grep test-app-checkpoint
```

## Step 10: Restore Checkpoint

### Restore from Image
```bash
# Deploy restored application
kubectl run restored-app --image=your-registry.com/test-app-checkpoint:latest

# Verify restoration
kubectl get pods restored-app
kubectl logs restored-app
```

## Quick Commands Reference

### Essential kubectl Commands
```bash
# Check cluster status
kubectl cluster-info

# List nodes
kubectl get nodes

# Check DaemonSet
kubectl get daemonset -n snap

# View pod logs
kubectl logs test-app
```

### Essential SNAP API Commands
```bash
# Check API health
curl http://localhost:8000/health

# List clusters
curl http://localhost:8000/cluster/list

# List checkpoints
curl http://localhost:8000/checkpoint/list

# Get cluster status
curl http://localhost:8000/cluster/status/production-cluster
```

## What's Next?

Now that you have SNAP running:

1. **Explore the [API Documentation](api-endpoints.md)**
2. **Set up [Automation Workflows](automation.md)**
3. **Configure [Security Settings](security.md)**
4. **Learn about [Advanced Features](advanced-features.md)**

## Troubleshooting

### Common Issues

#### Checkpoint Creation Fails
- Verify pod is running: `kubectl get pods`
- Check node permissions: `kubectl describe node`
- Review API logs: `docker-compose logs snapapi`

#### Registry Push Fails
- Verify registry credentials
- Check network connectivity
- Review registry logs

#### SnapWatcher Not Starting
- Verify cluster permissions
- Check operator logs
- Ensure DaemonSet is deployed

### Getting Help

- **Documentation**: Check relevant guides
- **Issues**: [GitHub Issues](https://github.com/weaversoftio/Snap/issues)
- **Support**: support@weaversoft.io

## Success!

Congratulations! You've successfully:
- ✅ Installed and configured SNAP
- ✅ Connected to your Openshift cluster
- ✅ Created your first checkpoint
- ✅ Converted checkpoint to container image
- ✅ Restored application from checkpoint

You're now ready to use SNAP for production container checkpointing and migration workflows!
