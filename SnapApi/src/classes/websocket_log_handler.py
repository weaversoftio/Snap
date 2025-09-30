"""
WebSocket Log Handler for SnapApi
Sends all logger.info, logger.error, and logger.warning messages to the System Logs section via WebSocket.
"""

import logging
import asyncio
import json
from datetime import datetime
from typing import Optional
import threading
from queue import Queue, Empty


class WebSocketLogHandler(logging.Handler):
    """
    Custom logging handler that sends log messages to connected WebSocket clients.
    This handler captures logger.info, logger.error, and logger.warning messages
    and forwards them to the System Logs section in the UI.
    """
    
    def __init__(self, send_progress_func=None):
        super().__init__()
        self.send_progress_func = send_progress_func
        self.log_queue = Queue()
        self.thread = None
        self.running = False
        
        # Start the background thread to process logs
        self.start_processing()
    
    def start_processing(self):
        """Start the background thread to process log messages."""
        if self.thread is None or not self.thread.is_alive():
            self.running = True
            self.thread = threading.Thread(target=self._process_logs, daemon=True)
            self.thread.start()
    
    def stop_processing(self):
        """Stop the background thread."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)
    
    def emit(self, record):
        """
        Emit a log record to the WebSocket clients.
        This method is called by the logging system for each log message.
        """
        try:
            # Only process info, error, and warning levels
            if record.levelno not in [logging.INFO, logging.ERROR, logging.WARNING]:
                return
            
            # Format the log message (just the message part, not the full formatted log)
            log_message = record.getMessage()
            
            # Determine log type based on level
            log_type = 'info'
            if record.levelno == logging.ERROR:
                log_type = 'error'
            elif record.levelno == logging.WARNING:
                log_type = 'warning'
            
            # Create log data structure matching the expected format
            # Determine progress value based on log type
            if log_type == 'error':
                progress = "failed"
            elif log_type == 'success':
                progress = 100
            else:  # info or warning
                progress = 50
            
            # Extract initiator, task, and message from record args if available
            initiator, task_name, message = self._extract_log_components(record, log_message)
            
            log_data = {
                'message': message,
                'task_name': task_name,
                'progress': progress,
                'cluster': 'default',
                'initiator': initiator
            }
            
            # Add to queue for processing
            self.log_queue.put(log_data)
            
        except Exception as e:
            # Avoid infinite recursion by not logging errors from the handler
            print(f"Error in WebSocketLogHandler.emit: {e}")
    
    def _process_logs(self):
        """Background thread to process log messages and send them via WebSocket."""
        while self.running:
            try:
                # Get log data from queue with timeout
                log_data = self.log_queue.get(timeout=1)
                
                # Send via WebSocket if function is available
                if self.send_progress_func:
                    try:
                        # Create a new event loop for this thread
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(self.send_progress_func(log_data))
                        finally:
                            loop.close()
                    except Exception as e:
                        print(f"Error sending log via WebSocket: {e}")
                
                self.log_queue.task_done()
                
            except Empty:
                # Timeout occurred, continue loop
                continue
            except Exception as e:
                print(f"Error processing log: {e}")
    
    def set_send_progress_func(self, send_progress_func):
        """Set the function to use for sending progress messages."""
        self.send_progress_func = send_progress_func
    
    def _extract_log_components(self, record, log_message):
        """
        Extract initiator, task, and message from log record.
        Supports both explicit logging (with extra args) and automatic extraction.
        
        Args:
            record: Log record object
            log_message: The log message
            
        Returns:
            tuple: (initiator, task_name, message)
        """
        # Check if record has extra fields (explicit logging)
        if hasattr(record, 'log_initiator') and hasattr(record, 'log_task'):
            return record.log_initiator, record.log_task, log_message
        
        # Check if args contain initiator and task (from structured logging)
        if hasattr(record, 'args') and len(record.args) >= 2:
            try:
                # Try to extract from args if they're structured
                if isinstance(record.args[0], dict):
                    extra_data = record.args[0]
                    initiator = extra_data.get('log_initiator', self._extract_initiator(record.name, log_message))
                    task = extra_data.get('log_task', self._extract_task_name(log_message, 'info'))
                    message = extra_data.get('log_message', log_message)
                    return initiator, task, message
            except (IndexError, AttributeError, TypeError):
                pass
        
        # Fallback to automatic extraction
        initiator = self._extract_initiator(record.name, log_message)
        task_name = self._extract_task_name(log_message, 'info')
        return initiator, task_name, log_message
    
    def _extract_initiator(self, logger_name, log_message):
        """
        Dynamically extract initiator from logger name and log message.
        
        Args:
            logger_name: Name of the logger (e.g., 'automation_api', 'automation_api.SnapWatcher')
            log_message: The log message content
            
        Returns:
            str: The initiator name
        """
        # Extract initiator from logger hierarchy
        if '.' in logger_name:
            # For hierarchical loggers like 'automation_api.SnapWatcher'
            parts = logger_name.split('.')
            if len(parts) > 1:
                return parts[-1]  # Use the last part (e.g., 'SnapWatcher')
        
        # Extract initiator from log message if it contains component names
        message_lower = log_message.lower()
        if 'snapwatcher:' in message_lower:
            return 'SnapWatcher'
        elif 'snaphook:' in message_lower:
            return 'SnapHook'
        elif 'cluster login' in message_lower:
            return 'SnapApi'
        elif 'checkpoint' in message_lower:
            return 'SnapApi'
        elif 'webhook' in message_lower:
            return 'SnapHook'
        
        # Default fallback
        return 'SnapApi'
    
    def _extract_task_name(self, log_message, log_type):
        """
        Dynamically extract task name from log message content.
        
        Args:
            log_message: The log message content
            log_type: The log type (info, warning, error, success)
            
        Returns:
            str: The task name
        """
        message_lower = log_message.lower()
        
        # Common task patterns
        task_patterns = [
            ('ssl verification', 'SSL Configuration'),
            ('configured kubernetes client', 'Kubernetes Setup'),
            ('operator started successfully', 'Operator Start'),
            ('will watch', 'Monitoring Setup'),
            ('processing checkpoint request', 'Checkpoint Processing'),
            ('auto-deleting pod', 'Pod Management'),
            ('kubernetes client not ready', 'Client Status'),
            ('auto-generated webhook url', 'Webhook Configuration'),
            ('generating self-signed certificates', 'Certificate Generation'),
            ('successfully generated', 'Certificate Generation'),
            ('resolved', 'Network Configuration'),
            ('generated ip addresses', 'Network Configuration'),
            ('received webhook request', 'Webhook Processing'),
            ('processing pod', 'Pod Mutation'),
            ('webhook response sent', 'Response Handling'),
            ('logged in to the kubernetes cluster', 'Cluster Login'),
            ('current user:', 'Cluster Login'),
            ('current context:', 'Cluster Login'),
            ('loaded', 'Configuration Loading'),
            ('watcher config', 'Configuration Loading'),
            ('config loaded', 'Configuration Loading'),
            ('config saved', 'Configuration Saving'),
            ('config deleted', 'Configuration Deletion'),
            ('failed to', 'Error Handling'),
            ('error', 'Error Handling'),
            ('exception', 'Error Handling'),
            ('started:', 'Operation Start'),
            ('stopped:', 'Operation Stop'),
            ('created:', 'Operation Create'),
            ('deleted:', 'Operation Delete'),
            ('updated:', 'Operation Update'),
        ]
        
        # Check for specific task patterns
        for pattern, task_name in task_patterns:
            if pattern in message_lower:
                return task_name
        
        # Extract task from common operation patterns
        if 'start' in message_lower and ('operator' in message_lower or 'watcher' in message_lower):
            return 'Operation Start'
        elif 'stop' in message_lower and ('operator' in message_lower or 'watcher' in message_lower):
            return 'Operation Stop'
        elif 'create' in message_lower:
            return 'Operation Create'
        elif 'delete' in message_lower:
            return 'Operation Delete'
        elif 'update' in message_lower:
            return 'Operation Update'
        
        # Default based on log type
        if log_type == 'error':
            return 'Error Handling'
        elif log_type == 'success':
            return 'Operation Success'
        else:
            return 'General Operation'
    
    def close(self):
        """Clean up the handler."""
        self.stop_processing()
        super().close()


# Global instance for easy access
websocket_log_handler = None


def setup_websocket_logging(send_progress_func=None):
    """
    Setup WebSocket logging for SnapApi.
    
    Args:
        send_progress_func: Function to send progress messages via WebSocket
    """
    global websocket_log_handler
    
    # Create the handler
    websocket_log_handler = WebSocketLogHandler(send_progress_func)
    
    # Configure the handler
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    websocket_log_handler.setFormatter(formatter)
    websocket_log_handler.setLevel(logging.INFO)
    
    # Add handler to the automation_api logger (main SnapApi logger)
    automation_logger = logging.getLogger("automation_api")
    
    # Check if handler already exists to avoid duplicates
    handler_exists = any(isinstance(h, WebSocketLogHandler) for h in automation_logger.handlers)
    if not handler_exists:
        automation_logger.addHandler(websocket_log_handler)
    
    return websocket_log_handler


def update_websocket_logging(send_progress_func):
    """
    Update the WebSocket function for the existing handler.
    
    Args:
        send_progress_func: Function to send progress messages via WebSocket
    """
    global websocket_log_handler
    
    if websocket_log_handler:
        websocket_log_handler.set_send_progress_func(send_progress_func)


def cleanup_websocket_logging():
    """Clean up the WebSocket logging handler."""
    global websocket_log_handler
    
    if websocket_log_handler:
        websocket_log_handler.close()
        websocket_log_handler = None


# Helper functions for explicit logging
def log_with_context(logger, level, initiator, task, message, **kwargs):
    """
    Log with explicit initiator, task, and message.
    
    Args:
        logger: Logger instance
        level: Log level (logging.INFO, logging.ERROR, etc.)
        initiator: The initiator (e.g., 'SnapWatcher', 'SnapHook')
        task: The task name (e.g., 'SSL Configuration', 'Operator Start')
        message: The log message
        **kwargs: Additional context
    """
    extra = {
        'log_initiator': initiator,
        'log_task': task,
        'log_message': message,
        **kwargs
    }
    logger.log(level, message, extra=extra)


def log_info(logger, initiator, task, message, **kwargs):
    """Log info message with explicit context."""
    log_with_context(logger, logging.INFO, initiator, task, message, **kwargs)


def log_error(logger, initiator, task, message, **kwargs):
    """Log error message with explicit context."""
    log_with_context(logger, logging.ERROR, initiator, task, message, **kwargs)


def log_warning(logger, initiator, task, message, **kwargs):
    """Log warning message with explicit context."""
    log_with_context(logger, logging.WARNING, initiator, task, message, **kwargs)


def log_success(logger, initiator, task, message, **kwargs):
    """Log success message with explicit context."""
    log_with_context(logger, logging.INFO, initiator, task, message, **kwargs)
