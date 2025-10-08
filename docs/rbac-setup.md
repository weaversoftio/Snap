# RBAC Setup Guide for SnapAPI

This guide provides comprehensive instructions for setting up Role-Based Access Control (RBAC) for SnapAPI in OpenShift environments.

## Overview

SnapAPI requires specific Kubernetes RBAC permissions to perform container checkpointing operations, manage webhooks, and interact with cluster resources. This guide covers the complete RBAC setup process.

## Prerequisites

- OpenShift cluster access with admin privileges
- `oc` CLI tool installed and configured
- SnapAPI service account namespace (`snap`)

## RBAC Components

### 1. Service Account
- **Name**: `snapapi-serviceaccount`
- **Namespace**: `snap`
- **Purpose**: Provides identity for SnapAPI operations

### 2. Cluster Role
- **Name**: `snapapi-clusterrole`
- **Scope**: Cluster-wide permissions
- **Purpose**: Defines what SnapAPI can do

### 3. Cluster Role Binding
- **Name**: `snapapi-clusterrolebinding`
- **Purpose**: Links service account to cluster role

## Required Permissions

### Core Kubernetes API Group
```yaml
- apiGroups: [""]
  resources: 
    - "nodes"           # Required for checkpoint API access to nodes resource
    - "nodes/proxy"     # Required for checkpoint API subresource with CREATE permission
    - "pods"            # List, get, delete pods (auto-delete after checkpoint)
    - "pods/log"        # Required for oc debug node command (debug pod logs)
    - "pods/exec"       # Required for oc debug node command (debug pod execution)
    - "namespaces"      # Namespace operations
  verbs: ["get", "list", "watch", "create", "delete"]
```

### Apps API Group
```yaml
- apiGroups: ["apps"]
  resources: 
    - "replicasets"     # Template hash extraction
  verbs: ["get", "list"]
```

### OpenShift Security Context Constraints
```yaml
- apiGroups: ["security.openshift.io"]
  resources: 
    - "securitycontextconstraints"
  verbs: ["use"]
  resourceNames: ["privileged"]
```

### Admission Webhook Configuration
```yaml
- apiGroups: ["admissionregistration.k8s.io"]
  resources: 
    - "mutatingwebhookconfigurations"
    - "validatingwebhookconfigurations"
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
```

## Permission Usage Details

### Checkpoint Operations
- **`nodes`**: Access to node information for checkpoint API calls
- **`nodes/proxy`**: Required for `/api/v1/nodes/{node_name}/proxy/checkpoint/...` endpoints
- **`pods`**: Fetch pod information, delete pods after checkpointing
- **`pods/log`**: Access debug pod logs during `oc debug node` operations
- **`pods/exec`**: Execute commands in debug pods during checkpoint operations

### Webhook Management
- **`mutatingwebhookconfigurations`**: Create and manage SnapHook webhooks
- **`validatingwebhookconfigurations`**: Manage webhook validation rules

### OpenShift Integration
- **`securitycontextconstraints`**: Use privileged SCC for `oc debug node` operations

### Template Operations
- **`replicasets`**: Extract template hashes for container identification

## Automated Setup

### Using the Setup Script

SnapAPI includes an automated RBAC setup script:

```bash
cd SnapApi
./setup-snapapi-rbac.sh
```

This script will:
1. Create the `snap` namespace if it doesn't exist
2. Apply the RBAC configuration
3. Generate a permanent service account token
4. Verify all permissions
5. Save configuration to `snapapi-config.json`

### Manual Setup

#### Step 1: Create Namespace
```bash
oc new-project snap --skip-config-write
```

#### Step 2: Apply RBAC Configuration
```bash
oc apply -f snapapi-rbac.yaml
```

#### Step 3: Create Permanent Token
```bash
# Create token secret
oc apply -f snapapi-token-secret.yaml

# Extract token
TOKEN=$(oc get secret snapapi-serviceaccount-token -n snap -o jsonpath='{.data.token}' | base64 -d)
echo "Token: $TOKEN"
```

#### Step 4: Verify Permissions
```bash
# Test core permissions
oc auth can-i get pods --as=system:serviceaccount:snap:snapapi-serviceaccount
oc auth can-i get nodes --as=system:serviceaccount:snap:snapapi-serviceaccount
oc auth can-i create nodes/proxy --as=system:serviceaccount:snap:snapapi-serviceaccount
oc auth can-i get pods/log --as=system:serviceaccount:snap:snapapi-serviceaccount
oc auth can-i create pods/exec --as=system:serviceaccount:snap:snapapi-serviceaccount
oc auth can-i create mutatingwebhookconfigurations --as=system:serviceaccount:snap:snapapi-serviceaccount
oc auth can-i use securitycontextconstraints/privileged --as=system:serviceaccount:snap:snapapi-serviceaccount
```

## Configuration Files

### snapapi-rbac.yaml
```yaml
---
# SnapAPI Service Account RBAC Configuration for OpenShift
apiVersion: v1
kind: ServiceAccount
metadata:
  name: snapapi-serviceaccount
  namespace: snap
automountServiceAccountToken: true
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: snapapi-clusterrole
rules:
  # Core Kubernetes API Group - Complete permissions for checkpoint operations
  - apiGroups: [""]
    resources: 
      - "nodes"           # Required for checkpoint API access to nodes resource
      - "nodes/proxy"     # Required for checkpoint API subresource with CREATE permission
      - "pods"            # List, get, delete pods (auto-delete after checkpoint)
      - "pods/log"        # Required for oc debug node command (debug pod logs)
      - "pods/exec"       # Required for oc debug node command (debug pod execution)
      - "namespaces"      # Namespace operations
    verbs: ["get", "list", "watch", "create", "delete"]

  # Apps API Group - ReplicaSet operations only
  - apiGroups: ["apps"]
    resources: 
      - "replicasets"     # Template hash extraction
    verbs: ["get", "list"]

  # OpenShift Security Context Constraints
  - apiGroups: ["security.openshift.io"]
    resources: 
      - "securitycontextconstraints"
    verbs: ["use"]
    resourceNames: ["privileged"]

  # Admission Webhook Configuration
  - apiGroups: ["admissionregistration.k8s.io"]
    resources: 
      - "mutatingwebhookconfigurations"
      - "validatingwebhookconfigurations"
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: snapapi-clusterrolebinding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: snapapi-clusterrole
subjects:
- kind: ServiceAccount
  name: snapapi-serviceaccount
  namespace: snap
```

### snapapi-token-secret.yaml
```yaml
---
apiVersion: v1
kind: Secret
metadata:
  name: snapapi-serviceaccount-token
  namespace: snap
  annotations:
    kubernetes.io/service-account.name: snapapi-serviceaccount
type: kubernetes.io/service-account-token
```

## Token Configuration

### Getting the Token
```bash
# Method 1: From secret
TOKEN=$(oc get secret snapapi-serviceaccount-token -n snap -o jsonpath='{.data.token}' | base64 -d)

# Method 2: From service account
TOKEN=$(oc get secret -n snap -o jsonpath='{.items[?(@.metadata.annotations.kubernetes\.io/service-account\.name=="snapapi-serviceaccount")].data.token}' | base64 -d)
```

### Using the Token in SnapAPI
```json
{
  "cluster_config_details": {
    "kube_api_url": "https://api.crc.testing:6443",
    "token": "eyJhbGciOiJSUzI1NiIsImtpZCI6IlItZG9QMzdPTWttM3B1cmNKTEoyX0xaa3FkZkNOdDNZLW1hT0Q1c1BONVUifQ..."
  },
  "name": "snap"
}
```

## Troubleshooting

### Common Issues

#### Permission Denied Errors
```bash
# Check if service account exists
oc get serviceaccount snapapi-serviceaccount -n snap

# Check cluster role binding
oc get clusterrolebinding snapapi-clusterrolebinding

# Verify permissions
oc auth can-i get pods --as=system:serviceaccount:snap:snapapi-serviceaccount
```

#### Token Issues
```bash
# Check token secret
oc get secret snapapi-serviceaccount-token -n snap

# Verify token is valid
oc auth can-i get pods --as=system:serviceaccount:snap:snapapi-serviceaccount --token=<TOKEN>
```

#### Debug Pod Issues
```bash
# Test debug pod creation
oc debug node/<node-name> -- chroot /host echo "test"

# Check SCC permissions
oc auth can-i use securitycontextconstraints/privileged --as=system:serviceaccount:snap:snapapi-serviceaccount
```

### Verification Commands

```bash
# Complete permission verification
echo "=== SnapAPI RBAC Verification ==="
echo "Can get pods: $(oc auth can-i get pods --as=system:serviceaccount:snap:snapapi-serviceaccount)"
echo "Can get nodes: $(oc auth can-i get nodes --as=system:serviceaccount:snap:snapapi-serviceaccount)"
echo "Can create nodes/proxy: $(oc auth can-i create nodes/proxy --as=system:serviceaccount:snap:snapapi-serviceaccount)"
echo "Can get pods/log: $(oc auth can-i get pods/log --as=system:serviceaccount:snap:snapapi-serviceaccount)"
echo "Can create pods/exec: $(oc auth can-i create pods/exec --as=system:serviceaccount:snap:snapapi-serviceaccount)"
echo "Can create mutatingwebhookconfigurations: $(oc auth can-i create mutatingwebhookconfigurations --as=system:serviceaccount:snap:snapapi-serviceaccount)"
echo "Can use privileged SCC: $(oc auth can-i use securitycontextconstraints/privileged --as=system:serviceaccount:snap:snapapi-serviceaccount)"
```

## Security Considerations

### Principle of Least Privilege
- Only required permissions are granted
- No unnecessary API group access
- Minimal verb permissions per resource

### Token Management
- Tokens are generated with 1-year expiration
- Tokens are stored securely in Kubernetes secrets
- Regular token rotation recommended

### Audit Logging
- All RBAC operations are logged
- Failed permission attempts are tracked
- Service account usage is monitored

## Best Practices

1. **Regular Audits**: Periodically review and audit RBAC permissions
2. **Token Rotation**: Rotate service account tokens regularly
3. **Monitoring**: Monitor for unusual permission usage patterns
4. **Documentation**: Keep RBAC documentation up to date
5. **Testing**: Test permissions in non-production environments first

## Support

For RBAC-related issues:
- Check the [Troubleshooting Guide](troubleshooting.md)
- Review OpenShift RBAC documentation
- Contact support at support@weaversoft.io
