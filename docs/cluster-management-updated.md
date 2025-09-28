# Cluster Management

This guide covers how to manage Openshift and Kubernetes clusters in SNAP with the new DaemonSet-based approach.

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

## DaemonSet-Based Cluster Monitoring

### Deploy Cluster Monitor DaemonSet
```bash
kubectl apply -f SnapApi/snap-cluster-monitor-daemonset.yaml
```

### Automatic Node Status Reporting
The DaemonSet automatically:
- **Monitors cluster health**: Real-time cluster status
- **Reports node status**: Individual node checkpointing capabilities
- **Manages configurations**: Node-level configuration management
- **Updates UI**: Sends status updates to SNAP UI

### Check Cluster Status
- **Dashboard**: Real-time cluster health from DaemonSet
- **Node Status**: Automatic node status from DaemonSet
- **Resource Usage**: CPU, memory, and storage metrics
- **Checkpointing Status**: Automatic checkpointing capability verification

## Deprecated Features (No Longer Used)

The following features are **deprecated** and no longer needed after DaemonSet deployment:

### ❌ Manual Cluster Verification
- ~~`/cluster/verify_checkpointing`~~ - Replaced by DaemonSet monitoring
- ~~Manual cluster health checks~~ - Automatic via DaemonSet

### ❌ Manual Checkpointing Enablement
- ~~`/cluster/enable_checkpointing`~~ - Handled by DaemonSet
- ~~Manual runC installation~~ - Managed by DaemonSet

### ❌ Manual runC Installation
- ~~`/cluster/install_runc`~~ - Automatic via DaemonSet
- ~~Manual node configuration~~ - Managed by DaemonSet

### ❌ Manual Node Configuration
- ~~Manual node setup~~ - Automatic via DaemonSet
- ~~Manual playbook execution~~ - Integrated into DaemonSet

### ❌ Manual Playbook Configuration
- ~~Manual playbook management~~ - Built into DaemonSet
- ~~Manual cluster setup scripts~~ - Automated via DaemonSet

## New Workflow

### 1. Add Cluster (UI/API)
- Configure basic cluster information
- Set up authentication
- Select registry (optional)

### 2. Deploy DaemonSet
```bash
kubectl apply -f SnapApi/snap-cluster-monitor-daemonset.yaml
```

### 3. Automatic Configuration
The DaemonSet automatically:
- Enables checkpointing on nodes
- Installs required runC versions
- Configures node settings
- Monitors cluster health
- Reports status to UI

### 4. Monitor via UI
- View real-time cluster status
- Monitor node health
- Track checkpointing capabilities
- Review cluster metrics

## Troubleshooting Cluster Issues

### Common Problems
- **Connection Failed**: Check network connectivity and credentials
- **Permission Denied**: Verify RBAC permissions for DaemonSet
- **DaemonSet Not Deploying**: Check cluster permissions and namespace access
- **No Status Updates**: Verify DaemonSet is running and communicating with UI

### Diagnostic Commands
```bash
# Check cluster connectivity
kubectl cluster-info

# Verify node status
kubectl get nodes -o wide

# Check DaemonSet status
kubectl get daemonset -n snap

# View DaemonSet logs
kubectl logs -n snap daemonset/snapwatcher

# Check DaemonSet pods
kubectl get pods -n snap -l app=snapwatcher
```

## API Changes

### Removed Endpoints
These API endpoints are **no longer available**:
- `POST /cluster/enable_checkpointing`
- `POST /cluster/install_runc`
- `POST /cluster/verify_checkpointing`
- `POST /cluster/configure_nodes`
- `POST /cluster/run_playbook`

### Active Endpoints
These endpoints remain active:
- `GET /cluster/statistics` - Cluster statistics
- `GET /cluster/status/{cluster_name}` - Cluster status from DaemonSet
- `POST /cluster/add` - Add new cluster
- `PUT /cluster/update` - Update cluster configuration
- `DELETE /cluster/delete` - Remove cluster

## Migration Guide

### From Old to New Approach

1. **Remove manual configurations**:
   - Delete manual checkpointing enablement scripts
   - Remove manual runC installation scripts
   - Clean up manual node configuration scripts

2. **Deploy DaemonSet**:
   ```bash
   kubectl apply -f SnapApi/snap-cluster-monitor-daemonset.yaml
   ```

3. **Verify DaemonSet deployment**:
   ```bash
   kubectl get daemonset -n snap
   kubectl get pods -n snap -l app=snapwatcher
   ```

4. **Monitor via UI**:
   - Check cluster dashboard for status
   - Verify node status updates
   - Monitor checkpointing capabilities

## Benefits of DaemonSet Approach

### Automation
- **Automatic configuration**: No manual setup required
- **Self-healing**: Automatic recovery from failures
- **Consistent state**: Uniform configuration across all nodes

### Monitoring
- **Real-time status**: Continuous cluster health monitoring
- **Proactive alerts**: Early detection of issues
- **Centralized reporting**: All status in one place

### Maintenance
- **Reduced complexity**: Single DaemonSet manages everything
- **Easier updates**: Update DaemonSet for configuration changes
- **Better reliability**: Built-in redundancy and failover
