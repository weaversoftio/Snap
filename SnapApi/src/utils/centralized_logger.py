"""
Centralized logging system for SnapApi
Handles both file logging and UI streaming with proper categorization
"""

import os
import json
import threading
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

class CentralizedLogger:
    def __init__(self, log_file_path: str = "/tmp/snapapi_logs.txt"):
        self.log_file_path = Path(log_file_path)
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        
        # Initialize log file
        with open(self.log_file_path, 'w') as f:
            f.write(f"# SnapApi Logs - Started at {datetime.now().isoformat()}\n")
            f.write("# Format: [TIMESTAMP] [INITIATOR] [LEVEL] - MESSAGE\n\n")
    
    def _write_to_file(self, initiator: str, level: str, message: str):
        """Write log entry to file with proper formatting."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        log_entry = f"{timestamp} - {level} - [{initiator}] {message}\n"
        
        with self.lock:
            with open(self.log_file_path, 'a') as f:
                f.write(log_entry)
                f.flush()
    
    def _should_show_in_ui(self, initiator: str, message: str) -> bool:
        """Determine if log should be shown in UI based on initiator."""
        # Only show logs from our main components
        return initiator in ["SnapWatcher", "SnapHook", "SnapApi"]
    
    def log_info(self, message: str, initiator: str = "SnapApi", show_in_ui: bool = True):
        """Log info message."""
        self._write_to_file(initiator, "INFO", message)
        
        if show_in_ui and self._should_show_in_ui(initiator, message):
            self._stream_to_ui(initiator, "info", message)
    
    def log_error(self, message: str, initiator: str = "SnapApi", show_in_ui: bool = True):
        """Log error message."""
        self._write_to_file(initiator, "ERROR", message)
        
        if show_in_ui and self._should_show_in_ui(initiator, message):
            self._stream_to_ui(initiator, "error", message)
    
    def log_warning(self, message: str, initiator: str = "SnapApi", show_in_ui: bool = True):
        """Log warning message."""
        self._write_to_file(initiator, "WARNING", message)
        
        if show_in_ui and self._should_show_in_ui(initiator, message):
            self._stream_to_ui(initiator, "warning", message)
    
    def log_success(self, message: str, initiator: str = "SnapApi", show_in_ui: bool = True):
        """Log success message."""
        self._write_to_file(initiator, "SUCCESS", message)
        
        if show_in_ui and self._should_show_in_ui(initiator, message):
            self._stream_to_ui(initiator, "success", message)
    
    def log_debug(self, message: str, initiator: str = "SnapApi", show_in_ui: bool = False):
        """Log debug message (usually not shown in UI)."""
        self._write_to_file(initiator, "DEBUG", message)
        
        if show_in_ui and self._should_show_in_ui(initiator, message):
            self._stream_to_ui(initiator, "debug", message)
    
    def _stream_to_ui(self, initiator: str, level: str, message: str):
        """Stream log to UI via the existing log buffer."""
        try:
            from routes.logs import add_log_to_buffer
            import uuid
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = {
                "id": str(uuid.uuid4()),
                "timestamp": timestamp,
                "message": message,
                "level": level,
                "initiator": initiator,
                "raw_line": message
            }
            add_log_to_buffer(log_entry)
        except ImportError:
            # If routes.logs is not available, just skip UI streaming
            pass
    
    def get_recent_logs(self, lines: int = 100) -> list:
        """Get recent log entries from file."""
        try:
            with open(self.log_file_path, 'r') as f:
                all_lines = f.readlines()
                # Filter out comment lines and empty lines
                log_lines = [line.strip() for line in all_lines 
                           if line.strip() and not line.strip().startswith('#')]
                return log_lines[-lines:] if log_lines else []
        except FileNotFoundError:
            return []
    
    def clear_logs(self):
        """Clear the log file."""
        with self.lock:
            with open(self.log_file_path, 'w') as f:
                f.write(f"# SnapApi Logs - Cleared at {datetime.now().isoformat()}\n")
                f.write("# Format: [TIMESTAMP] [INITIATOR] [LEVEL] - MESSAGE\n\n")

# Global logger instance
centralized_logger = CentralizedLogger()

# Convenience functions for easy import
def log_info(message: str, initiator: str = "SnapApi", show_in_ui: bool = True):
    centralized_logger.log_info(message, initiator, show_in_ui)

def log_error(message: str, initiator: str = "SnapApi", show_in_ui: bool = True):
    centralized_logger.log_error(message, initiator, show_in_ui)

def log_warning(message: str, initiator: str = "SnapApi", show_in_ui: bool = True):
    centralized_logger.log_warning(message, initiator, show_in_ui)

def log_success(message: str, initiator: str = "SnapApi", show_in_ui: bool = True):
    centralized_logger.log_success(message, initiator, show_in_ui)

def log_debug(message: str, initiator: str = "SnapApi", show_in_ui: bool = False):
    centralized_logger.log_debug(message, initiator, show_in_ui)
