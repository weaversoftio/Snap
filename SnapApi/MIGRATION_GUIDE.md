# Migration Guide: Explicit Logging for SnapWatcher and SnapHook

## Overview
This guide shows how to migrate from automatic log extraction to explicit logging with initiator, task, and message parameters.

## Benefits of Explicit Logging
- **Precise Control**: You specify exactly what initiator, task, and message should appear in the UI
- **Consistent Format**: All logs follow the same structure regardless of message content
- **Better Categorization**: Tasks are properly categorized (e.g., "SSL Configuration", "Operator Start")
- **Future-Proof**: Works with any new components or log messages

## How to Use Explicit Logging

### 1. Import the Helper Functions
```python
from classes.websocket_log_handler import log_info, log_error, log_warning, log_success
```

### 2. Replace Existing Logger Calls

#### Before (Automatic Extraction):
```python
logger.info('SSL verification disabled for cluster crc2')
logger.error('Failed to process webhook request: Invalid payload')
logger.warning('Will watch for pod events in namespace: default')
```

#### After (Explicit Logging):
```python
log_info(logger, 'SnapWatcher', 'SSL Configuration', 'SSL verification disabled for cluster crc2')
log_error(logger, 'SnapHook', 'Error Handling', 'Failed to process webhook request: Invalid payload')
log_warning(logger, 'SnapWatcher', 'Monitoring Setup', 'Will watch for pod events in namespace: default')
```

### 3. Available Helper Functions

- `log_info(logger, initiator, task, message)` - For informational messages
- `log_error(logger, initiator, task, message)` - For error messages
- `log_warning(logger, initiator, task, message)` - For warning messages
- `log_success(logger, initiator, task, message)` - For success messages

### 4. Common Initiator Values
- `'SnapWatcher'` - For SnapWatcher component
- `'SnapHook'` - For SnapHook component
- `'SnapApi'` - For SnapApi component

### 5. Common Task Values
- `'SSL Configuration'` - SSL-related operations
- `'Kubernetes Setup'` - Kubernetes client configuration
- `'Operator Start'` - Operator startup
- `'Monitoring Setup'` - Event monitoring configuration
- `'Webhook Configuration'` - Webhook setup
- `'Certificate Generation'` - Certificate operations
- `'Webhook Processing'` - Webhook request handling
- `'Pod Mutation'` - Pod modification operations
- `'Response Handling'` - Response processing
- `'Configuration Loading'` - Config file operations
- `'Cluster Login'` - Authentication operations
- `'Error Handling'` - Error processing
- `'Pod Management'` - Pod lifecycle operations
- `'Pod Event Processing'` - Pod event handling

## Migration Steps

### Step 1: Update SnapWatcher Class
Replace all `logger.info()`, `logger.error()`, `logger.warning()` calls with explicit logging:

```python
# In SnapWatcher class
from classes.websocket_log_handler import log_info, log_error, log_warning, log_success

# Replace:
# logger.info('SSL verification disabled for cluster crc2')
# With:
log_info(self.logger, 'SnapWatcher', 'SSL Configuration', 'SSL verification disabled for cluster crc2')
```

### Step 2: Update SnapHook Class
Replace all logger calls with explicit logging:

```python
# In SnapHook class
from classes.websocket_log_handler import log_info, log_error, log_warning, log_success

# Replace:
# logger.info('Auto-generated webhook URL: https://webhook.example.com/mutate')
# With:
log_info(self.logger, 'SnapHook', 'Webhook Configuration', 'Auto-generated webhook URL: https://webhook.example.com/mutate')
```

### Step 3: Update SnapApi Class
Replace logger calls with explicit logging:

```python
# In SnapApi class
from classes.websocket_log_handler import log_info, log_error, log_warning, log_success

# Replace:
# logger.info('Loaded 2 watcher configs')
# With:
log_info(self.logger, 'SnapApi', 'Configuration Loading', 'Loaded 2 watcher configs')
```

## Backward Compatibility
The system still supports automatic extraction for any logger calls that don't use explicit logging. This means you can migrate gradually without breaking existing functionality.

## Example Migration

### Before:
```python
class SnapWatcherOperator:
    def __init__(self):
        self.logger = logging.getLogger("automation_api.SnapWatcher")
    
    def start_operator(self, cluster_name):
        self.logger.info(f'SSL verification disabled for cluster {cluster_name}')
        self.logger.info(f'Configured Kubernetes client for cluster {cluster_name}')
        self.logger.info(f'operator started successfully for cluster: {cluster_name}')
```

### After:
```python
class SnapWatcherOperator:
    def __init__(self):
        self.logger = logging.getLogger("automation_api.SnapWatcher")
    
    def start_operator(self, cluster_name):
        log_info(self.logger, 'SnapWatcher', 'SSL Configuration', f'SSL verification disabled for cluster {cluster_name}')
        log_info(self.logger, 'SnapWatcher', 'Kubernetes Setup', f'Configured Kubernetes client for cluster {cluster_name}')
        log_success(self.logger, 'SnapWatcher', 'Operator Start', f'operator started successfully for cluster: {cluster_name}')
```

## Result in System Logs UI
With explicit logging, the System Logs will show:
- **Initiator**: SnapWatcher, SnapHook, SnapApi (as specified)
- **Task**: SSL Configuration, Operator Start, etc. (as specified)
- **Message**: The exact message you provide
- **Type**: info, error, warning, success (based on the function used)
- **Time**: Automatic timestamp

This gives you complete control over how logs appear in the UI while maintaining the dynamic WebSocket integration.
