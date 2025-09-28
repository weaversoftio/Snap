# API Endpoints Reference

Complete reference for all SNAP API endpoints.

## Base URL

```
http://localhost:8000
```

## Authentication

Most endpoints require authentication. Include the token in the Authorization header:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/endpoint
```

## Checkpoint Endpoints

### Create Checkpoint
```http
POST /checkpoint/kubelet/checkpoint
```

**Request Body:**
```json
{
  "pod_name": "test-app",
  "namespace": "default",
  "node_name": "worker-node-1",
  "container_name": "test-app",
  "cluster_name": "production-cluster"
}
```

**Response:**
```json
{
  "success": true,
  "pod_id": "pod-12345",
  "container_ids": ["container-67890"],
  "checkpoint_path": "/app/checkpoints/test-app-12345.tar",
  "message": "Checkpoint created successfully"
}
```

### Create Checkpoint and Push
```http
POST /checkpoint/kubelet/checkpoint-and-push
```

**Query Parameters:**
- `pod_name`: Pod name
- `node_name`: Node name
- `container_name`: Container name
- `checkpoint_config_name`: Checkpoint configuration name

**Request Body:**
```json
{
  "namespace": "default",
  "cluster": "production-cluster",
  "registry": "nexus-registry",
  "image_name": "test-app-checkpoint",
  "tag": "latest"
}
```

### List Checkpoints
```http
GET /checkpoint/list
```

**Response:**
```json
{
  "checkpoints": [
    {
      "id": "checkpoint-123",
      "pod_name": "test-app",
      "namespace": "default",
      "created_at": "2024-01-15T10:30:00Z",
      "size": "150MB",
      "status": "completed"
    }
  ]
}
```

### Download Checkpoint
```http
GET /checkpoint/download/{pod_name}/{filename}
```

### Checkpoint Insights
```http
POST /checkpoint/insights
```

**Request Body:**
```json
{
  "checkpoint_path": "/app/checkpoints/test-app-12345.tar",
  "analysis_type": "volatility"
}
```

## Cluster Endpoints

### Enable Checkpointing
```http
POST /cluster/enable_checkpointing
```

**Request Body:**
```json
{
  "cluster_name": "production-cluster",
  "node_names": ["worker-node-1", "worker-node-2"]
}
```

### Install runC
```http
POST /cluster/install_runc
```

**Request Body:**
```json
{
  "cluster_name": "production-cluster",
  "runc_version": "1.2.4"
}
```

### Verify Checkpointing
```http
POST /cluster/verify_checkpointing
```

**Request Body:**
```json
{
  "cluster_name": "production-cluster"
}
```

**Response:**
```json
{
  "cluster_name": "production-cluster",
  "checkpointing_enabled": true,
  "nodes": [
    {
      "name": "worker-node-1",
      "runc_version": "1.2.4",
      "criu_available": true
    }
  ]
}
```

### Get Cluster Statistics
```http
GET /cluster/statistics
```

## Registry Endpoints

### Login to Registry
```http
POST /registry/login
```

**Request Body:**
```json
{
  "registry_config_name": "nexus-registry"
}
```

### Create and Push Checkpoint Container
```http
POST /registry/create_and_push_checkpoint_container
```

**Request Body:**
```json
{
  "checkpoint_name": "test-app-checkpoint",
  "username": "admin",
  "pod_name": "test-app",
  "checkpoint_config_name": "default"
}
```

## Configuration Endpoints

### Registry Configuration

#### Create Registry Config
```http
POST /config/registry/create
```

**Request Body:**
```json
{
  "name": "nexus-registry",
  "url": "https://nexus.company.com",
  "username": "admin",
  "password": "password123",
  "verify_ssl": true
}
```

#### List Registry Configs
```http
GET /config/registry/list
```

#### Update Registry Config
```http
PUT /config/registry/update
```

#### Delete Registry Config
```http
DELETE /config/registry/delete
```

### Cluster Configuration

#### Create Cluster Config
```http
POST /config/clusters/create
```

**Request Body:**
```json
{
  "name": "production-cluster",
  "api_server_url": "https://api.cluster.com:6443",
  "auth_type": "kubeconfig",
  "kubeconfig_content": "base64-encoded-kubeconfig",
  "registry_name": "nexus-registry"
}
```

#### List Cluster Configs
```http
GET /config/clusters/list
```

#### Update Cluster Config
```http
PUT /config/clusters/update
```

#### Delete Cluster Config
```http
DELETE /config/clusters/delete
```

### User Configuration

#### Create User
```http
POST /config/user/create
```

**Request Body:**
```json
{
  "username": "admin",
  "password": "securepassword",
  "email": "admin@company.com",
  "role": "administrator"
}
```

#### Login User
```http
POST /config/user/login
```

**Request Body:**
```json
{
  "username": "admin",
  "password": "securepassword"
}
```

**Response:**
```json
{
  "success": true,
  "token": "jwt-token-here",
  "user": {
    "username": "admin",
    "role": "administrator"
  }
}
```

## Automation Endpoints

### Trigger Automation
```http
POST /automation/trigger
```

**Request Body:**
```json
{
  "pod_name": "test-app",
  "namespace": "default",
  "node_name": "worker-node-1",
  "container_name": "test-app",
  "cluster_name": "production-cluster",
  "registry": "nexus-registry",
  "username": "admin",
  "password": "password123"
}
```

## Operator Endpoints

### Start SnapWatcher
```http
POST /operator/start
```

**Request Body:**
```json
{
  "cluster_name": "production-cluster",
  "cluster_config": {
    "api_server_url": "https://api.cluster.com:6443",
    "auth_type": "kubeconfig"
  },
  "scope": "cluster",
  "namespace": "snap",
  "auto_delete_pod": true
}
```

### Stop SnapWatcher
```http
POST /operator/stop
```

**Request Body:**
```json
{
  "cluster_name": "production-cluster"
}
```

### Get Operator Status
```http
GET /operator/status
```

**Response:**
```json
{
  "running": true,
  "active_watchers": [
    {
      "cluster_name": "production-cluster",
      "status": "active",
      "started_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

## SnapHook Endpoints

### Create SnapHook
```http
POST /snaphook
```

**Request Body:**
```json
{
  "name": "production-snaphook",
  "cluster_name": "production-cluster",
  "cluster_config": {
    "api_server_url": "https://api.cluster.com:6443"
  },
  "webhook_url": "https://snap.company.com/webhook",
  "namespace": "snap",
  "cert_expiry_days": 365
}
```

### Start SnapHook
```http
POST /snaphook/{name}/start
```

### Stop SnapHook
```http
POST /snaphook/{name}/stop
```

### List SnapHooks
```http
GET /snaphook/list
```

## WebSocket Endpoints

### Progress Updates
```http
WS /ws/progress
```

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/progress');
ws.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('Progress:', data);
};
```

## Error Responses

All endpoints may return error responses in this format:

```json
{
  "success": false,
  "error": "Error message",
  "details": "Detailed error information",
  "code": "ERROR_CODE"
}
```

### Common Error Codes

- `AUTHENTICATION_FAILED`: Invalid or missing authentication
- `CLUSTER_NOT_FOUND`: Specified cluster not found
- `REGISTRY_CONNECTION_FAILED`: Cannot connect to registry
- `CHECKPOINT_FAILED`: Checkpoint creation failed
- `PERMISSION_DENIED`: Insufficient permissions
- `VALIDATION_ERROR`: Invalid request parameters

## Rate Limiting

API requests are rate-limited:
- **Authenticated users**: 1000 requests per hour
- **Unauthenticated users**: 100 requests per hour

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642233600
```

## Examples

### Complete Checkpoint Workflow
```bash
# 1. Create checkpoint
CHECKPOINT_RESPONSE=$(curl -X POST "http://localhost:8000/checkpoint/kubelet/checkpoint" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "pod_name": "test-app",
    "namespace": "default",
    "node_name": "worker-node-1",
    "container_name": "test-app",
    "cluster_name": "production-cluster"
  }')

# 2. Convert to image
curl -X POST "http://localhost:8000/registry/create_and_push_checkpoint_container" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "checkpoint_name": "test-app-checkpoint",
    "username": "admin",
    "pod_name": "test-app",
    "checkpoint_config_name": "default"
  }'
```

### Cluster Management
```bash
# Enable checkpointing on cluster
curl -X POST "http://localhost:8000/cluster/enable_checkpointing" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "cluster_name": "production-cluster",
    "node_names": ["worker-node-1", "worker-node-2"]
  }'

# Verify checkpointing is enabled
curl -X POST "http://localhost:8000/cluster/verify_checkpointing" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"cluster_name": "production-cluster"}'
```
