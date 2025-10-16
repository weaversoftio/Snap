"""
Logs API endpoint for SnapApi
Captures SnapApi's own stdout/stderr output and displays it in the UI
"""

import asyncio
import json
import logging
import sys
import io
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
import threading

from middleware.verify_token import verify_token

router = APIRouter()
logger = logging.getLogger("automation_api")

# Store recent logs in memory (circular buffer)
MAX_LOG_ENTRIES = 1000
recent_logs: List[Dict[str, Any]] = []
log_buffer_lock = threading.Lock()

def add_log_to_buffer(log_entry: Dict[str, Any]):
    """Add a log entry to the circular buffer."""
    global recent_logs
    
    with log_buffer_lock:
        recent_logs.append(log_entry)
        # Keep only the most recent entries
        if len(recent_logs) > MAX_LOG_ENTRIES:
            recent_logs = recent_logs[-MAX_LOG_ENTRIES:]

# Custom stdout/stderr capture
class LogCapture:
    def __init__(self, original_stream, log_level="info"):
        self.original_stream = original_stream
        self.log_level = log_level
        self.buffer = io.StringIO()
    
    def write(self, message):
        # Write to original stream
        self.original_stream.write(message)
        self.original_stream.flush()
        
        # Also capture for our logs
        if message.strip():  # Only capture non-empty messages
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = {
                "timestamp": timestamp,
                "message": message.strip(),
                "level": self.log_level,
                "initiator": "SnapApi",
                "raw_line": message.strip()
            }
            add_log_to_buffer(log_entry)
    
    def flush(self):
        self.original_stream.flush()
    
    def __getattr__(self, name):
        return getattr(self.original_stream, name)

# Set up stdout/stderr capture
original_stdout = sys.stdout
original_stderr = sys.stderr
sys.stdout = LogCapture(original_stdout, "info")
sys.stderr = LogCapture(original_stderr, "error")

# Add initial test log
print("SnapApi logs capture initialized successfully")


@router.get("/container")
async def get_container_logs(username: str = Depends(verify_token)):
    """
    Get SnapApi stdout/stderr logs.
    Returns the captured stdout/stderr output from the SnapApi process.
    """
    try:
        logger.info(f"Fetching captured logs for user: {username}")
        
        with log_buffer_lock:
            logs_to_return = recent_logs[-100:]  # Return last 100 entries
            
        logger.info(f"Returning {len(logs_to_return)} captured log entries")
        
        return {
            "logs": logs_to_return,
            "source": "captured",
            "total_lines": len(logs_to_return)
        }
        
    except Exception as e:
        logger.error(f"Failed to get captured logs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get captured logs: {str(e)}"
        )

@router.get("/container/stream")
async def stream_container_logs(username: str = Depends(verify_token)):
    """
    Stream SnapApi captured logs in real-time.
    Returns a streaming response with live captured stdout/stderr.
    """
    async def generate_logs():
        """Generator function for streaming logs."""
        try:
            # Send initial logs
            with log_buffer_lock:
                initial_logs = recent_logs[-20:]  # Send last 20 lines
            
            for log in initial_logs:
                yield f"data: {json.dumps(log)}\n\n"
            
            # Stream new logs
            last_log_count = len(initial_logs)
            while True:
                await asyncio.sleep(1)  # Check every second
                
                with log_buffer_lock:
                    current_logs = recent_logs
                
                # Find new logs
                if len(current_logs) > last_log_count:
                    new_logs = current_logs[last_log_count:]
                    last_log_count = len(current_logs)
                    
                    # Send new logs
                    for log in new_logs:
                        yield f"data: {json.dumps(log)}\n\n"
                
                # Keep buffer size manageable
                if last_log_count > 200:
                    last_log_count = max(0, last_log_count - 100)
                    
        except Exception as e:
            error_log = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "message": f"Error streaming logs: {str(e)}",
                "level": "error",
                "initiator": "SnapApi"
            }
            yield f"data: {json.dumps(error_log)}\n\n"
    
    return StreamingResponse(
        generate_logs(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )

@router.get("/recent")
async def get_recent_logs(limit: int = 50, username: str = Depends(verify_token)):
    """
    Get recent logs from the in-memory buffer.
    """
    with log_buffer_lock:
        return {
            "logs": recent_logs[-limit:],
            "total": len(recent_logs)
        }

@router.post("/add")
async def add_log_entry(log_entry: Dict[str, Any], username: str = Depends(verify_token)):
    """
    Add a log entry to the buffer (for internal use).
    """
    add_log_to_buffer(log_entry)
    return {"status": "success", "message": "Log entry added"}

@router.delete("/clear")
async def clear_logs(username: str = Depends(verify_token)):
    """
    Clear the log buffer.
    """
    global recent_logs
    with log_buffer_lock:
        recent_logs.clear()
    return {"status": "success", "message": "Logs cleared"}

# Function to be called by the logging system to add logs to buffer
def add_application_log(level: str, message: str, initiator: str = "SnapApi"):
    """Add application log to the buffer."""
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "message": message,
        "level": level,
        "initiator": initiator
    }
    add_log_to_buffer(log_entry)
