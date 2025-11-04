# Checkpointing Guide

Learn how to create, manage, and restore container checkpoints with SNAP.

## Creating Checkpoints

### Via Web Interface
1. Navigate to **Checkpoints**
2. Click **Create Checkpoint**
3. Fill in details:
   - Pod Name
   - Namespace
   - Container Name
   - Cluster

### Via API
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

## Checkpoint Types

### Single Container Checkpoint
- Captures one container's state
- Faster checkpoint creation
- Smaller checkpoint size

### Multi-Container Pod Checkpoint
- Captures entire pod state
- Includes all containers
- Preserves pod-level networking

## Converting Checkpoints to Images

### Automatic Conversion
```bash
curl -X POST "http://localhost:8000/checkpoint/kubelet/checkpoint-and-push" \
  -H "Content-Type: application/json" \
  -d '{
    "namespace": "default",
    "cluster": "production-cluster",
    "registry": "nexus-registry",
    "image_name": "test-app-checkpoint",
    "tag": "latest"
  }'
```

### Manual Conversion
1. Create checkpoint first
2. Navigate to **Checkpoints**
3. Select checkpoint
4. Click **Convert to Image**
5. Configure image details

## Restoring Checkpoints

### From Image
```bash
kubectl run restored-app --image=your-registry.com/test-app-checkpoint:latest
```

### From Checkpoint File
1. Download checkpoint file
2. Upload to target cluster
3. Use restore API endpoint

## Best Practices

### Checkpoint Timing
- **During low activity**: Minimize application impact
- **Scheduled checkpoints**: Use automation for regular backups
- **Before updates**: Create checkpoints before deployments

### Storage Management
- **Regular cleanup**: Remove old checkpoints
- **Compression**: Enable checkpoint compression
- **Registry cleanup**: Manage registry storage

### Performance Optimization
- **Resource allocation**: Ensure adequate resources
- **Network optimization**: Use fast storage
- **Parallel checkpoints**: Limit concurrent operations
