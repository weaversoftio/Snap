# Frequently Asked Questions (FAQ)

## General Questions

### What is SNAP?
SNAP is an enterprise-grade container checkpointing and state management platform that enables organizations to capture the complete runtime state of running containers, convert them into portable images, and restore them across different environments.

### What does "SNAP it, Save it, Start again" mean?
This is SNAP's tagline representing the core workflow:
- **SNAP it**: Capture the complete state of a running container
- **Save it**: Store the checkpoint as a portable image
- **Start again**: Restore the container state in any environment

### How is SNAP different from regular container backups?
Unlike traditional backups that only capture data, SNAP captures the complete runtime state including:
- Memory state and process information
- Network connections and file descriptors
- Application state and running processes
- Container runtime environment

## Technical Questions

### What container runtimes does SNAP support?
SNAP supports:
- **CRI-O**: Primary runtime for Openshift
- **containerd**: Kubernetes default runtime
- **Docker**: Legacy container runtime
- **Podman**: Rootless container runtime

### What Kubernetes distributions are supported?
SNAP works with:
- **Openshift**: All versions 4.8+
- **Kubernetes**: All versions 1.21+
- **EKS**: Amazon Elastic Kubernetes Service
- **GKE**: Google Kubernetes Engine
- **AKS**: Azure Kubernetes Service
- **Rancher**: Rancher-managed clusters

### How does checkpointing work?
SNAP uses CRIU (Checkpoint/Restore in Userspace) technology:
1. **Capture**: Freezes the container and captures memory, processes, and file system state
2. **Serialize**: Converts the state into a portable format
3. **Store**: Saves the checkpoint as a tar file or container image
4. **Restore**: Recreates the exact container state from the checkpoint

### What is the difference between SnapWatcher and SnapHook?
- **SnapWatcher**: Operator that runs inside SnapAPI, monitors containers and performs automatic checkpointing
- **SnapHook**: Webhook system that provides event-driven automation and CI/CD integration

### Do I need to deploy the DaemonSet?
Yes, the cluster monitor DaemonSet is required for:
- Real-time cluster health monitoring
- Node-level configuration management
- Cluster status reporting
- Checkpointing capability verification

## Installation & Setup

### What are the system requirements?
**Minimum Requirements:**
- 4GB RAM
- 20GB free disk space
- Docker 20.10+
- Docker Compose 2.0+
- kubectl access

**Recommended:**
- 8GB+ RAM
- 50GB+ free disk space
- SSD storage for better performance

### Can I install SNAP on a private cluster?
Yes, SNAP supports private clusters. You'll need:
- Network access to the cluster API server
- Valid kubeconfig or authentication token
- Registry access for image storage

### How do I configure registry authentication?
1. Navigate to **Configuration > Registry**
2. Add registry details (URL, credentials)
3. Test connectivity
4. Select the registry when configuring clusters

### What ports does SNAP use?
- **SnapAPI**: 8000 (HTTP), 8443 (HTTPS/webhooks)
- **SnapUI**: 3000 (HTTP)
- **SnapWatcher**: Uses cluster API (no additional ports)

## Usage Questions

### How long does checkpointing take?
Checkpoint time depends on:
- **Container size**: Larger containers take longer
- **Memory usage**: More memory = longer checkpoint time
- **Network activity**: Active connections may delay checkpointing
- **Storage speed**: SSD vs HDD affects performance

**Typical times:**
- Small containers (< 1GB): 10-30 seconds
- Medium containers (1-4GB): 30-120 seconds
- Large containers (> 4GB): 2-10 minutes

### Can I checkpoint multi-container pods?
Yes, SNAP supports:
- **Single container**: Checkpoint individual containers
- **Multi-container pods**: Checkpoint all containers in a pod
- **Selective checkpointing**: Choose specific containers to checkpoint

### What happens to running applications during checkpointing?
- **Applications continue running**: No downtime during checkpoint creation
- **Brief pause**: Minimal pause (milliseconds) when capturing state
- **No data loss**: All application state is preserved
- **Network connections**: Maintained during checkpointing

### Can I restore checkpoints to different clusters?
Yes, SNAP supports cross-cluster restoration:
- **Same architecture**: Restore to identical cluster configurations
- **Different clusters**: Restore to different Openshift/Kubernetes clusters
- **Cloud migration**: Move from on-premises to cloud or between clouds
- **Version upgrades**: Restore to newer cluster versions

## Security Questions

### Is checkpoint data encrypted?
SNAP provides multiple encryption options:
- **In transit**: SSL/TLS for all API communications
- **At rest**: Optional encryption for stored checkpoints
- **Registry**: Uses registry's built-in encryption
- **Network**: Secure communication between components

### How does authentication work?
SNAP supports multiple authentication methods:
- **Token-based**: JWT tokens for API access
- **RBAC**: Role-based access control
- **LDAP/AD**: Enterprise directory integration
- **OAuth**: Third-party authentication providers

### Can I audit checkpoint operations?
Yes, SNAP provides comprehensive audit logging:
- **Operation logs**: All checkpoint create/restore operations
- **User activity**: Who performed what actions
- **System events**: Cluster and component status changes
- **Compliance reports**: SOC 2, GDPR compliance features

## Troubleshooting

### Why is checkpointing failing?
Common causes and solutions:
- **Insufficient permissions**: Check cluster RBAC settings
- **Storage space**: Ensure adequate disk space
- **Network issues**: Verify cluster connectivity
- **CRI-O version**: Update to supported CRI-O version
- **Node resources**: Check CPU and memory availability

### How do I check if checkpointing is enabled?
```bash
# Check cluster status
curl http://localhost:8000/cluster/verify_checkpointing \
  -H "Content-Type: application/json" \
  -d '{"cluster_name": "your-cluster"}'

# Check node status
kubectl get nodes -o wide
kubectl describe node <node-name>
```

### Why is the SnapWatcher operator not starting?
Check these common issues:
- **Cluster permissions**: Verify operator has necessary RBAC
- **Resource limits**: Check if cluster has sufficient resources
- **Network policies**: Ensure network connectivity
- **Configuration**: Verify cluster configuration is correct

### How do I troubleshoot registry push failures?
1. **Verify credentials**: Test registry login manually
2. **Check network**: Ensure registry is accessible
3. **Review logs**: Check SnapAPI logs for detailed errors
4. **Test connectivity**: Use registry health check endpoints

## Performance Questions

### How does checkpointing affect application performance?
- **Minimal impact**: Checkpointing has negligible performance impact
- **Brief pause**: Only during state capture (milliseconds)
- **No downtime**: Applications continue running normally
- **Resource usage**: Minimal additional CPU/memory usage

### What's the maximum container size for checkpointing?
SNAP can checkpoint containers of any size, but performance considerations:
- **Small containers** (< 1GB): Optimal performance
- **Medium containers** (1-10GB): Good performance
- **Large containers** (> 10GB): Slower but functional
- **Very large containers** (> 50GB): May require significant time

### How much storage space do checkpoints require?
Checkpoint size depends on:
- **Container memory**: Primary factor in checkpoint size
- **File system changes**: Modified files since container start
- **Compression**: SNAP compresses checkpoints to reduce size

**Typical sizes:**
- Small containers: 100MB - 500MB
- Medium containers: 500MB - 2GB
- Large containers: 2GB - 10GB

## Integration Questions

### Can I integrate SNAP with CI/CD pipelines?
Yes, SNAP provides multiple integration options:
- **SnapHook webhooks**: Event-driven automation
- **REST API**: Programmatic access to all features
- **CLI tools**: Command-line interface for scripting
- **Kubernetes operators**: Native Kubernetes integration

### Does SNAP work with GitOps?
Yes, SNAP is GitOps-compatible:
- **Configuration as code**: All settings stored in Git
- **Automated deployments**: CI/CD pipeline integration
- **Version control**: Track checkpoint and configuration changes
- **Rollback capabilities**: Restore previous states

### Can I use SNAP with monitoring tools?
SNAP integrates with popular monitoring solutions:
- **Prometheus**: Metrics collection and alerting
- **Grafana**: Visualization and dashboards
- **ELK Stack**: Log aggregation and analysis
- **Datadog**: Application performance monitoring

## Licensing & Support

### What license does SNAP use?
SNAP is licensed under the MIT License, allowing:
- Commercial use
- Modification
- Distribution
- Private use

### How do I get support?
Multiple support channels available:
- **Documentation**: Comprehensive guides and tutorials
- **GitHub Issues**: Bug reports and feature requests
- **Community Forum**: Peer support and discussions
- **Enterprise Support**: Direct support for enterprise customers

### Is there a community version?
Yes, SNAP is open source with:
- **Full functionality**: All features available
- **Community support**: GitHub issues and forums
- **Regular updates**: Active development and releases
- **Enterprise features**: Additional support and services available

---

**Still have questions?** Check our [Troubleshooting Guide](troubleshooting.md) or [contact support](mailto:support@weaversoft.io).
