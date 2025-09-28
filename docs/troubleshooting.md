# Troubleshooting Guide

Common issues and solutions for SNAP deployments.

## Installation Issues

### Docker Compose Won't Start
**Problem**: Services fail to start with Docker Compose

**Solutions**:
```bash
# Check Docker status
docker --version
docker-compose --version

# Check port availability
netstat -tulpn | grep :8000
netstat -tulpn | grep :3000

# View detailed logs
docker-compose logs snapapi
docker-compose logs snapui
```

### Permission Issues
**Problem**: Permission denied errors

**Solutions**:
```bash
# Fix Docker permissions
sudo usermod -aG docker $USER
newgrp docker

# Check volume permissions
ls -la snapapi-checkpoints/
```

## Cluster Connection Issues

### Cluster Not Found
**Problem**: Cannot connect to cluster

**Solutions**:
1. **Verify kubeconfig**:
   ```bash
   kubectl cluster-info
   kubectl get nodes
   ```

2. **Check network connectivity**:
   ```bash
   curl -k https://your-cluster-api:6443/version
   ```

3. **Verify credentials**:
   ```bash
   kubectl auth can-i get pods
   ```

### Permission Denied
**Problem**: Insufficient permissions

**Solutions**:
1. **Check RBAC permissions**:
   ```bash
   kubectl auth can-i create pods
   kubectl auth can-i get nodes
   ```

2. **Verify service account**:
   ```bash
   kubectl get serviceaccounts
   kubectl describe serviceaccount snap-service-account
   ```

## Checkpointing Issues

### Checkpoint Creation Fails
**Problem**: Checkpoint creation fails

**Solutions**:
1. **Check pod status**:
   ```bash
   kubectl get pods
   kubectl describe pod <pod-name>
   ```

2. **Verify node permissions**:
   ```bash
   kubectl describe node <node-name>
   ```

3. **Check CRI-O version**:
   ```bash
   kubectl get nodes -o jsonpath='{.items[*].status.nodeInfo.containerRuntimeVersion}'
   ```

### Checkpoint Too Large
**Problem**: Checkpoint exceeds storage limits

**Solutions**:
1. **Increase storage**:
   ```bash
   kubectl patch pvc <pvc-name> -p '{"spec":{"resources":{"requests":{"storage":"50Gi"}}}}'
   ```

2. **Enable compression**:
   ```bash
   # Configure checkpoint compression in SNAP settings
   ```

## Registry Issues

### Registry Push Fails
**Problem**: Cannot push images to registry

**Solutions**:
1. **Verify credentials**:
   ```bash
   docker login your-registry.com
   ```

2. **Check network connectivity**:
   ```bash
   curl -k https://your-registry.com/v2/
   ```

3. **Review registry logs**:
   ```bash
   docker-compose logs snapapi | grep registry
   ```

### Authentication Failed
**Problem**: Registry authentication fails

**Solutions**:
1. **Test manual login**:
   ```bash
   docker login your-registry.com
   ```

2. **Check token validity**:
   ```bash
   curl -H "Authorization: Bearer <token>" https://your-registry.com/v2/
   ```

## Performance Issues

### Slow Checkpointing
**Problem**: Checkpointing takes too long

**Solutions**:
1. **Check resource usage**:
   ```bash
   kubectl top nodes
   kubectl top pods
   ```

2. **Optimize storage**:
   - Use SSD storage
   - Increase I/O capacity
   - Enable compression

3. **Reduce checkpoint size**:
   - Exclude unnecessary files
   - Use incremental checkpoints

### High Memory Usage
**Problem**: SNAP consumes too much memory

**Solutions**:
1. **Check memory limits**:
   ```bash
   docker stats snapapi snapui
   ```

2. **Optimize configuration**:
   - Reduce concurrent operations
   - Limit checkpoint retention
   - Optimize JVM settings

## Network Issues

### API Not Accessible
**Problem**: Cannot access SNAP API

**Solutions**:
1. **Check service status**:
   ```bash
   curl http://localhost:8000/health
   ```

2. **Verify firewall rules**:
   ```bash
   sudo ufw status
   sudo iptables -L
   ```

3. **Check port binding**:
   ```bash
   netstat -tulpn | grep :8000
   ```

### WebSocket Connection Fails
**Problem**: Real-time updates not working

**Solutions**:
1. **Check WebSocket endpoint**:
   ```bash
   curl -H "Upgrade: websocket" http://localhost:8000/ws/progress
   ```

2. **Verify proxy configuration**:
   - Check reverse proxy settings
   - Ensure WebSocket support
   - Verify CORS configuration

## Log Analysis

### Viewing Logs
```bash
# SNAP API logs
docker-compose logs snapapi

# SNAP UI logs
docker-compose logs snapui

# Kubernetes logs
kubectl logs -n snap <pod-name>

# System logs
journalctl -u docker
```

### Common Log Patterns
- **ERROR**: Critical issues requiring attention
- **WARN**: Potential problems or deprecated features
- **INFO**: Normal operation information
- **DEBUG**: Detailed debugging information

## Getting Help

### Diagnostic Information
When reporting issues, include:
- SNAP version
- Cluster information
- Error messages
- Log files
- System configuration

### Support Channels
- **Documentation**: Check relevant guides
- **GitHub Issues**: Report bugs and request features
- **Community Forum**: Get help from other users
- **Enterprise Support**: Direct support for enterprise customers
