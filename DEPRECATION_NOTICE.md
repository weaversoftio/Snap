# Deprecation Notice: Cluster Management Features

## Overview
Several cluster management features have been deprecated as they are now handled automatically by the DaemonSet deployment. These features are **disabled but not removed** to maintain backward compatibility and provide clear deprecation notices to users.

## Deprecated Features

### 1. Cluster Verification
- **API Endpoint**: `POST /cluster/verify_checkpointing`
- **UI Component**: "Verify Cluster" button
- **Status**: Disabled with deprecation message
- **Replacement**: Automatic monitoring via DaemonSet

### 2. Checkpointing Enablement
- **API Endpoint**: `POST /cluster/enable_checkpointing`
- **UI Component**: "Enable Checkpointing" button
- **Status**: Disabled with deprecation message
- **Replacement**: Automatic configuration via DaemonSet

### 3. runc Installation
- **API Endpoint**: `POST /cluster/install_runc`
- **UI Component**: "Install runc" button
- **Status**: Disabled with deprecation message
- **Replacement**: Automatic installation via DaemonSet

### 4. Node Configuration
- **API Endpoints**: 
  - `GET /config/cluster/node`
  - `PUT /config/cluster/nodes/edit`
- **UI Component**: "Node Config" button
- **Status**: Disabled with deprecation message
- **Replacement**: Automatic configuration via DaemonSet

### 5. Playbook Configuration
- **API Endpoints**:
  - `GET /config/playbooks/list`
  - `PUT /config/playbooks/update`
- **UI Component**: "Playbook Configs" button
- **Status**: Disabled with deprecation message
- **Replacement**: Integrated into DaemonSet

## Changes Made

### API Changes
All deprecated endpoints now return:
```json
{
  "success": false,
  "message": "This endpoint is deprecated. [Feature] is now handled automatically by the DaemonSet."
}
```

### UI Changes
1. **Deprecated buttons** are visually marked with:
   - Reduced opacity (0.6)
   - Dashed border style
   - Secondary text color
   - "(Deprecated)" suffix in button text
   - Tooltip explaining deprecation

2. **Deprecation notice section** added to cluster management UI with:
   - Warning icon and styling
   - List of deprecated features
   - Explanation of DaemonSet replacement
   - Clear messaging about automatic handling

3. **Handler functions** modified to show informational messages instead of executing deprecated functionality

## Migration Path

### For Users
1. **Deploy the DaemonSet**: Use `kubectl apply -f SnapApi/snap-cluster-monitor-daemonset.yaml`
2. **Monitor via UI**: The DaemonSet automatically reports cluster status to the UI
3. **No manual configuration needed**: All previously manual tasks are now automatic

### For Developers
- Deprecated endpoints remain in codebase for reference
- UI components remain visible but non-functional
- Clear deprecation messages guide users to new workflow
- No breaking changes to existing integrations

## Benefits of DaemonSet Approach

1. **Automatic Configuration**: No manual intervention required
2. **Real-time Monitoring**: Continuous cluster health monitoring
3. **Centralized Management**: Single point of control for cluster operations
4. **Reduced Complexity**: Eliminates need for manual playbook execution
5. **Better Reliability**: Automated processes reduce human error

## Timeline

- **Current**: Features are deprecated and show informational messages
- **Future**: Features may be completely removed in a future major version
- **Support**: Deprecated features will not receive updates or bug fixes

## Contact

For questions about the migration to DaemonSet-based cluster management, please refer to the cluster management documentation or contact the development team.
