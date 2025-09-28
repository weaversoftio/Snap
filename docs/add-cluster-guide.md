# Add Cluster Configuration

This guide walks you through adding a new cluster to SNAP using the web interface.

## Cluster Configuration Form

### Step 1: Basic Cluster Information

#### Cluster Name
- **Field**: Cluster Name
- **Required**: Yes
- **Description**: Unique identifier for your cluster
- **Example**: `production-cluster`, `staging-cluster`, `development-cluster`

#### Cluster API URL
- **Field**: Cluster Api Url
- **Required**: Yes
- **Description**: The Kubernetes/Openshift API server endpoint
- **Format**: `https://api.cluster.com:6443`
- **Examples**:
  - Openshift: `https://api.openshift.company.com:6443`
  - Kubernetes: `https://k8s-api.company.com:6443`
  - EKS: `https://EKS_CLUSTER_ID.region.eks.amazonaws.com`

#### Authentication Token
- **Field**: Token
- **Required**: Yes (if not using SSH key)
- **Description**: Authentication token for cluster access
- **Options**:
  - Service account token
  - User authentication token
  - Kubeconfig token

### Step 2: SSH Key Configuration

#### Upload SSH Key
- **Button**: Upload SSH Key
- **Purpose**: Secure cluster access for node operations
- **Required**: For node-level operations (checkpointing, runC installation)
- **Supported Formats**: RSA, ECDSA, Ed25519
- **Key Size**: Minimum 2048 bits for RSA

**How to generate SSH key:**
```bash
# Generate new SSH key
ssh-keygen -t rsa -b 4096 -C "snap-cluster-access"

# Copy public key
cat ~/.ssh/id_rsa.pub
```

**SSH Key Requirements:**
- Must have access to cluster nodes
- Should be added to authorized_keys on all nodes
- Requires sudo privileges for checkpointing operations

### Step 3: Registry Configuration

#### Registry Selection
- **Field**: Registry (Optional)
- **Purpose**: Container registry for checkpoint image storage
- **Options**:
  - Nexus Repository
  - Harbor
  - Docker Hub
  - Amazon ECR
  - Google GCR
  - Azure ACR

**Registry Benefits:**
- Store checkpoint images
- Enable cross-cluster restoration
- Version control for checkpoints
- Backup and disaster recovery

### Step 4: Submit Configuration

#### Submit Button
- **Action**: Submit
- **Process**: Validates and saves cluster configuration
- **Next Steps**: 
  - Deploy cluster monitor DaemonSet
  - Start SnapWatcher operator
  - Configure SnapHook webhooks

## Configuration Examples

### Openshift Cluster
```
Cluster Name: openshift-prod
Cluster Api Url: https://api.openshift.company.com:6443
Token: sha256~your-openshift-token-here
Registry: nexus-registry
```

### Kubernetes Cluster
```
Cluster Name: k8s-staging
Cluster Api Url: https://k8s-api.company.com:6443
Token: eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Registry: harbor-registry
```

### Amazon EKS
```
Cluster Name: eks-production
Cluster Api Url: https://EKS_CLUSTER_ID.us-west-2.eks.amazonaws.com
Token: k8s-aws-v1.eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Registry: amazon-ecr
```

## Post-Configuration Steps

### 1. Deploy Cluster Monitor DaemonSet
```bash
kubectl apply -f SnapApi/snap-cluster-monitor-daemonset.yaml
```

### 2. Verify Cluster Connection
```bash
# Test cluster connectivity
kubectl cluster-info

# Check node status
kubectl get nodes -o wide
```

### 3. Enable Checkpointing
```bash
curl -X POST http://localhost:8000/cluster/enable_checkpointing \
  -H "Content-Type: application/json" \
  -d '{
    "cluster_name": "your-cluster-name",
    "node_names": ["worker-node-1", "worker-node-2"]
  }'
```

### 4. Start SnapWatcher Operator
1. Navigate to **Operator > Start SnapWatcher**
2. Select your cluster
3. Click **Start SnapWatcher**

## Troubleshooting Cluster Addition

### Common Issues

#### Connection Failed
- **Cause**: Invalid API URL or network issues
- **Solution**: Verify cluster URL and network connectivity
- **Test**: `curl -k https://your-cluster-api:6443/version`

#### Authentication Failed
- **Cause**: Invalid token or expired credentials
- **Solution**: Generate new token or refresh credentials
- **Test**: `kubectl auth can-i get pods`

#### SSH Key Issues
- **Cause**: SSH key not properly configured on nodes
- **Solution**: Add public key to authorized_keys on all nodes
- **Test**: `ssh user@node-ip "sudo whoami"`

#### Registry Connection Failed
- **Cause**: Registry URL or credentials incorrect
- **Solution**: Verify registry configuration
- **Test**: `docker login your-registry.com`

### Validation Steps

1. **Test API Connection**:
   ```bash
   kubectl cluster-info
   kubectl get nodes
   ```

2. **Verify Permissions**:
   ```bash
   kubectl auth can-i create pods
   kubectl auth can-i get nodes
   kubectl auth can-i create daemonsets
   ```

3. **Check SSH Access**:
   ```bash
   ssh user@node-ip "sudo systemctl status crio"
   ```

4. **Test Registry Access**:
   ```bash
   docker login your-registry.com
   docker pull hello-world
   docker push your-registry.com/hello-world
   ```

## Best Practices

### Security
- Use service accounts with minimal required permissions
- Rotate tokens regularly
- Secure SSH key storage
- Enable SSL/TLS for all communications

### Performance
- Use dedicated nodes for checkpointing operations
- Ensure adequate storage space
- Monitor resource usage
- Optimize network connectivity

### Reliability
- Test cluster connectivity before adding
- Verify all prerequisites are met
- Monitor cluster health regularly
- Maintain backup configurations
