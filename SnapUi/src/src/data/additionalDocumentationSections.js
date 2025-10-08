// Additional documentation sections
export const additionalDocumentationSections = [
  {
    id: 'user-guides',
    title: 'User Guides',
    icon: '📖',
    pages: [
      {
        id: 'cluster-management',
        title: 'Cluster Management',
        content: `# Cluster Management

Learn how to manage Kubernetes/OpenShift clusters in SNAP.

## Adding Clusters

1. Navigate to the main cluster page
2. Click "Add Cluster" in the cluster selector
3. Fill in cluster details
4. Test connection and save

## Cluster Configuration

### Authentication Methods
- Token-based authentication
- Kubeconfig upload
- SSH key management

### Registry Integration
- Select registry for checkpoint images
- Configure repository settings
- Test registry connectivity

## Cluster Monitoring

### Health Checks
- API server connectivity
- Node status monitoring
- Resource availability

### Status Reporting
- Real-time cluster status
- Performance metrics
- Error notifications`
      },
      {
        id: 'checkpointing',
        title: 'Checkpointing Guide',
        content: `# Checkpointing Guide

Complete guide to creating and managing container checkpoints.

## Creating Checkpoints

### Via UI
1. Navigate to Checkpoints
2. Click "Create Checkpoint"
3. Select pod and container
4. Configure checkpoint settings
5. Start checkpoint process

### Via API
\`\`\`bash
curl -X POST "http://localhost:8000/checkpoint/kubelet/checkpoint" \\
  -H "Content-Type: application/json" \\
  -d '{
    "pod_name": "test-app",
    "namespace": "default",
    "node_name": "worker-node-1",
    "container_name": "test-app",
    "cluster_name": "production-cluster"
  }'
\`\`\`

## Checkpoint Management

### Viewing Checkpoints
- List all checkpoints
- Filter by cluster/namespace
- View checkpoint details

### Converting to Images
1. Select checkpoint
2. Click "Convert to Image"
3. Configure image settings
4. Push to registry

## Best Practices

### Checkpoint Timing
- Create checkpoints during low activity
- Schedule regular checkpoints
- Monitor resource usage

### Storage Management
- Clean up old checkpoints
- Monitor disk usage
- Configure retention policies`
      }
    ]
  },
  {
    id: 'api-reference',
    title: 'API Reference',
    icon: '🔌',
    pages: [
      {
        id: 'api-overview',
        title: 'API Overview',
        content: `# API Overview

Understanding the SNAP API structure and capabilities.

## Base URL
\`http://localhost:8000\`

## Authentication
All API calls require authentication via token:
\`\`\`
Authorization: Bearer <your-token>
\`\`\`

## API Endpoints

### Checkpoint Operations
- \`POST /checkpoint/kubelet/checkpoint\` - Create checkpoint
- \`GET /checkpoint/list\` - List checkpoints
- \`GET /checkpoint/download/{id}\` - Download checkpoint

### Cluster Management
- \`GET /cluster/list\` - List clusters
- \`POST /cluster/create\` - Add cluster
- \`DELETE /cluster/remove/{name}\` - Remove cluster

### Registry Operations
- \`GET /registry/list\` - List registries
- \`POST /registry/login\` - Test registry connection

## Response Format
\`\`\`json
{
  "success": true,
  "data": {...},
  "message": "Operation completed successfully"
}
\`\`\`

## Error Handling
\`\`\`json
{
  "success": false,
  "error": "Error message",
  "code": "ERROR_CODE"
}
\`\`\``
      }
    ]
  },
  {
    id: 'security-operations',
    title: 'Security & Operations',
    icon: '🔒',
    pages: [
      {
        id: 'rbac-setup',
        title: 'RBAC Setup Guide',
        content: `# RBAC Setup Guide

Complete guide to setting up Role-Based Access Control for SNAP.

## Automated Setup

\`\`\`bash
cd SnapApi
./setup-snapapi-rbac.sh
\`\`\`

## Required Permissions

### Core Kubernetes API
- **nodes**: Access to node information
- **nodes/proxy**: Checkpoint API operations
- **pods**: Pod management and debug operations
- **pods/log**: Debug pod logs
- **pods/exec**: Debug pod execution
- **namespaces**: Namespace operations

### Apps API
- **replicasets**: Template hash extraction

### OpenShift SCC
- **securitycontextconstraints**: Privileged operations

### Webhook Management
- **mutatingwebhookconfigurations**: SnapHook management
- **validatingwebhookconfigurations**: Webhook validation

## Verification

\`\`\`bash
# Test permissions
oc auth can-i get pods --as=system:serviceaccount:snap:snapapi-serviceaccount
oc auth can-i create nodes/proxy --as=system:serviceaccount:snap:snapapi-serviceaccount
oc auth can-i use securitycontextconstraints/privileged --as=system:serviceaccount:snap:snapapi-serviceaccount
\`\`\`

## Troubleshooting

### Permission Denied Errors
- Verify service account exists
- Check cluster role binding
- Ensure token is valid

### Debug Pod Issues
- Test debug pod creation
- Check SCC permissions
- Verify node access`
      }
    ]
  }
];

