# Registry Integration

Configure and manage container registries for checkpoint image storage.

## Supported Registries

### Nexus Repository
- **Nexus OSS**: Open source version
- **Nexus Pro**: Professional version
- **Nexus IQ**: Security scanning

### Harbor
- **Harbor OSS**: Open source registry
- **Harbor Enterprise**: Enterprise features

### Other Registries
- **Docker Hub**: Public registry
- **Amazon ECR**: AWS container registry
- **Google GCR**: Google container registry
- **Azure ACR**: Azure container registry

## Registry Configuration

### Adding Registry
1. Navigate to **Configuration > Registry**
2. Click **Add New Registry**
3. Configure:
   ```
   Registry Name: nexus-registry
   Registry URL: https://nexus.company.com
   Username: admin
   Password: password123
   Verify SSL: true
   ```

### Testing Connection
```bash
curl -X POST http://localhost:8000/registry/login \
  -H "Content-Type: application/json" \
  -d '{"registry_config_name": "nexus-registry"}'
```

## Registry Operations

### Login to Registry
- **Automatic**: SNAP handles authentication
- **Manual**: Use registry login API
- **Token-based**: Use authentication tokens

### Push Checkpoint Images
```bash
curl -X POST http://localhost:8000/registry/create_and_push_checkpoint_container \
  -H "Content-Type: application/json" \
  -d '{
    "checkpoint_name": "test-app-checkpoint",
    "username": "admin",
    "pod_name": "test-app",
    "checkpoint_config_name": "default"
  }'
```

## Registry Security

### Authentication Methods
- **Username/Password**: Basic authentication
- **Token-based**: API tokens
- **Certificate-based**: SSL certificates
- **OAuth**: Third-party authentication

### Security Best Practices
- **Use HTTPS**: Always use secure connections
- **Rotate credentials**: Regular password changes
- **Limit permissions**: Minimal required permissions
- **Monitor access**: Audit registry access logs

## Troubleshooting Registry Issues

### Common Problems
- **Authentication Failed**: Check credentials
- **Network Issues**: Verify connectivity
- **SSL Errors**: Check certificate validity
- **Permission Denied**: Verify registry permissions

### Diagnostic Steps
1. Test registry connectivity
2. Verify authentication
3. Check registry logs
4. Validate image push permissions
