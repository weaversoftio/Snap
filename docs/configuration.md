# Configuration Guide

Complete system configuration guide for SNAP deployments.

## System Configuration

### Environment Variables
```bash
# SNAP API configuration
export SNAP_API_URL=http://localhost:8000
export SNAP_ORIGINS=http://localhost:3000,*

# SnapWatcher configuration
export WATCHER_CLUSTER_NAME=production-cluster
export WATCHER_MODE=compose

# SSL configuration
export KUBE_VERIFY_SSL=false
export FLASK_ENV=development
```

### Docker Compose Configuration
```yaml
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
      - WATCHER_CLUSTER_NAME=production-cluster
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
```

## User Configuration

### Creating Users
```bash
curl -X POST http://localhost:8000/config/user/create \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "securepassword",
    "email": "admin@company.com",
    "role": "administrator"
  }'
```

### User Roles
- **Administrator**: Full system access
- **Operator**: Checkpoint operations
- **Viewer**: Read-only access
- **Custom**: Tailored permissions

## Cluster Configuration

### Adding Clusters
1. **Basic Configuration**:
   ```
   Cluster Name: production-cluster
   API Server URL: https://api.cluster.com:6443
   Authentication Type: kubeconfig
   ```

2. **Authentication Setup**:
   - Upload kubeconfig file
   - Or enter authentication token
   - Configure service account

3. **Registry Selection**:
   - Select configured registry
   - Enable image storage

## Registry Configuration

### Nexus Configuration
```json
{
  "name": "nexus-registry",
  "url": "https://nexus.company.com",
  "username": "admin",
  "password": "password123",
  "verify_ssl": true
}
```

### Harbor Configuration
```json
{
  "name": "harbor-registry",
  "url": "https://harbor.company.com",
  "username": "admin",
  "password": "password123",
  "verify_ssl": true
}
```

## Security Configuration

### SSL/TLS Setup
1. **Generate certificates**:
   ```bash
   openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
   ```

2. **Configure HTTPS**:
   ```yaml
   environment:
     - SSL_CERT_PATH=/app/cert.pem
     - SSL_KEY_PATH=/app/key.pem
   ```

### Authentication Configuration
```json
{
  "auth_method": "token",
  "token_expiry": 3600,
  "session_timeout": 1800,
  "max_login_attempts": 5
}
```

## Monitoring Configuration

### Prometheus Integration
```yaml
scrape_configs:
  - job_name: 'snap'
    static_configs:
      - targets: ['snapapi:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

### Logging Configuration
```json
{
  "log_level": "INFO",
  "log_format": "json",
  "log_rotation": "daily",
  "log_retention": "30d"
}
```
