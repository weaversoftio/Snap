# Security Guide

Security best practices and configuration for SNAP deployments.

## Authentication

### Token-based Authentication
```bash
# Generate token
curl -X POST http://localhost:8000/config/user/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "securepassword"
  }'
```

### RBAC Configuration

#### SnapAPI Service Account
SnapAPI uses a dedicated service account with specific cluster-wide permissions:

```bash
# Automated RBAC setup
cd SnapApi
./setup-snapapi-rbac.sh
```

#### Required Permissions
- **Nodes**: Access to node information and checkpoint API
- **Pods**: List, get, delete pods (including debug pods)
- **Webhooks**: Manage mutating and validating webhook configurations
- **SCC**: Use privileged Security Context Constraints for debug operations
- **ReplicaSets**: Extract template hashes for container identification

#### Permission Details
```yaml
# Core Kubernetes API Group
- apiGroups: [""]
  resources: ["nodes", "nodes/proxy", "pods", "pods/log", "pods/exec", "namespaces"]
  verbs: ["get", "list", "watch", "create", "delete"]

# Apps API Group
- apiGroups: ["apps"]
  resources: ["replicasets"]
  verbs: ["get", "list"]

# OpenShift Security Context Constraints
- apiGroups: ["security.openshift.io"]
  resources: ["securitycontextconstraints"]
  verbs: ["use"]
  resourceNames: ["privileged"]

# Admission Webhook Configuration
- apiGroups: ["admissionregistration.k8s.io"]
  resources: ["mutatingwebhookconfigurations", "validatingwebhookconfigurations"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
```

**For detailed RBAC setup instructions, see [RBAC Setup Guide](rbac-setup.md)**

## Network Security

### SSL/TLS Configuration
- **API Endpoints**: HTTPS for all API calls
- **Web Interface**: SSL certificates
- **Registry Communication**: Secure registry connections
- **Cluster Communication**: Encrypted cluster API calls

### Firewall Rules
```
# Allow SNAP API access
8000/tcp - SnapAPI HTTP
8443/tcp - SnapAPI HTTPS/Webhooks
3000/tcp - SnapUI (if external access needed)

# Block unnecessary ports
# Only allow required cluster ports
```

## Data Protection

### Checkpoint Encryption
- **At Rest**: Encrypt stored checkpoints
- **In Transit**: SSL/TLS for all transfers
- **Registry**: Use registry encryption features
- **Backup**: Encrypt backup storage

### Access Control
- **User Management**: Centralized user administration
- **Session Management**: Secure session handling
- **Audit Logging**: Comprehensive activity logs

## Compliance

### SOC 2 Compliance
- **Access Controls**: User authentication and authorization
- **Data Encryption**: Encrypt sensitive data
- **Audit Trails**: Comprehensive logging
- **Incident Response**: Security incident procedures

### GDPR Compliance
- **Data Minimization**: Collect only necessary data
- **Right to Erasure**: Data deletion capabilities
- **Data Portability**: Export user data
- **Privacy by Design**: Built-in privacy protection

## Security Monitoring

### Log Analysis
- **Authentication Logs**: Monitor login attempts
- **API Access Logs**: Track API usage
- **System Logs**: Monitor system events
- **Security Events**: Detect security incidents

### Alerting
- **Failed Logins**: Alert on authentication failures
- **Suspicious Activity**: Detect unusual patterns
- **System Compromise**: Monitor for security breaches
- **Compliance Violations**: Track policy violations
