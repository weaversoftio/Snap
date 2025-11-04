# API Overview

Introduction to the SNAP REST API and authentication methods.

## API Base URL

```
http://localhost:8000
```

## Authentication

SNAP uses token-based authentication. Include the token in the Authorization header:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/endpoint
```

### Getting an Authentication Token

1. **Login via API**:
   ```bash
   curl -X POST http://localhost:8000/config/user/login \
     -H "Content-Type: application/json" \
     -d '{
       "username": "admin",
       "password": "securepassword"
     }'
   ```

2. **Response**:
   ```json
   {
     "success": true,
     "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
     "user": {
       "username": "admin",
       "role": "administrator"
     }
   }
   ```

3. **Use the token**:
   ```bash
   curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
     http://localhost:8000/checkpoint/list
   ```

## API Endpoints Overview

### Checkpoint Endpoints
- `POST /checkpoint/kubelet/checkpoint` - Create checkpoint
- `GET /checkpoint/list` - List checkpoints
- `GET /checkpoint/download/{pod_name}/{filename}` - Download checkpoint

### Cluster Endpoints
- `POST /cluster/enable_checkpointing` - Enable checkpointing
- `POST /cluster/verify_checkpointing` - Verify checkpointing
- `GET /cluster/statistics` - Get cluster statistics

### Registry Endpoints
- `POST /registry/login` - Login to registry
- `POST /registry/create_and_push_checkpoint_container` - Push checkpoint image

### Configuration Endpoints
- `POST /config/clusters/create` - Create cluster config
- `POST /config/registry/create` - Create registry config
- `POST /config/user/create` - Create user

## Response Format

All API responses follow this format:

### Success Response
```json
{
  "success": true,
  "data": {
    "checkpoint_id": "checkpoint-123",
    "status": "completed"
  },
  "message": "Operation completed successfully"
}
```

### Error Response
```json
{
  "success": false,
  "error": "Error message",
  "details": "Detailed error information",
  "code": "ERROR_CODE"
}
```

## Error Codes

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

Rate limit headers:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642233600
```

## WebSocket Support

Real-time updates via WebSocket:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/progress');
ws.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('Progress:', data);
};
```

## API Documentation

Interactive API documentation is available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI Spec**: `http://localhost:8000/openapi.json`
