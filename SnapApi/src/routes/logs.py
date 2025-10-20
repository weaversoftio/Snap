"""
Logs API endpoint for SnapApi
Reads logs from centralized log file and streams them to the UI
"""

import asyncio
import json
import logging
import sys
import io
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
import threading

from middleware.verify_token import verify_token
from utils.centralized_logger import centralized_logger

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

def parse_log_line(log_line: str) -> Optional[Dict[str, Any]]:
    """Parse a log line from the centralized log file."""
    try:
        # Expected format: "2025-10-19 10:52:06,870 - INFO - [SnapHook] STOP request: hook2"
        parts = log_line.split(" - ", 2)
        if len(parts) != 3:
            return None
        
        timestamp_str = parts[0]
        level = parts[1]
        message_part = parts[2]
        
        # Extract initiator from message if it's in brackets
        initiator = "SnapApi"  # Default
        message = message_part
        
        if message_part.startswith("[") and "]" in message_part:
            end_bracket = message_part.find("]")
            initiator = message_part[1:end_bracket]
            message = message_part[end_bracket + 2:].strip()
        
        # Convert timestamp to UI format
        try:
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
            timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            timestamp = timestamp_str
        
        return {
            "id": str(uuid.uuid4()),
            "timestamp": timestamp,
            "message": message,
            "level": level.lower(),
            "initiator": initiator,
            "raw_line": log_line
        }
    except Exception:
        return None

def load_logs_from_file() -> List[Dict[str, Any]]:
    """Load logs from the centralized log file."""
    log_lines = centralized_logger.get_recent_logs(200)
    parsed_logs = []
    
    for line in log_lines:
        parsed_log = parse_log_line(line)
        if parsed_log:
            parsed_logs.append(parsed_log)
    
    return parsed_logs

# Initialize centralized logging
centralized_logger.log_info("SnapApi centralized logging initialized successfully", "SnapApi")

# Old LogCapture system removed - now using centralized logging


@router.get("/container")
async def get_container_logs(username: str = Depends(verify_token)):
    """
    Get SnapApi logs from centralized log file.
    Returns logs from the centralized logging system.
    """
    try:
        # Get logs from memory buffer only (for real-time updates)
        with log_buffer_lock:
            logs_to_return = recent_logs[-100:]  # Get last 100 logs
        
        return {
            "logs": logs_to_return,
            "source": "centralized_file",
            "total_lines": len(logs_to_return)
        }
        
    except Exception as e:
        centralized_logger.log_error(f"Failed to get logs: {e}", "SnapApi")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get logs: {str(e)}"
        )

@router.get("/stream")
async def stream_logs(username: str = Depends(verify_token)):
    """Stream logs using Server-Sent Events (SSE)."""
    async def event_generator():
        last_log_count = 0
        
        while True:
            with log_buffer_lock:
                current_log_count = len(recent_logs)
                
                if current_log_count > last_log_count:
                    # New logs available
                    new_logs = recent_logs[last_log_count:]
                    last_log_count = current_log_count
                    
                    for log in new_logs:
                        yield f"data: {json.dumps(log)}\n\n"
                else:
                    # No new logs, send keep-alive
                    yield f"data: {json.dumps({'type': 'keepalive', 'timestamp': datetime.now().isoformat()})}\n\n"
            
            await asyncio.sleep(1)  # Check every second
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
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
            # Track seen log IDs to prevent duplicates
            seen_log_ids = set()
            
            # Get the current log count to only track NEW logs after this point
            with log_buffer_lock:
                initial_log_count = len(recent_logs)
            
            # Stream new logs
            while True:
                await asyncio.sleep(1)  # Check every second
                
                with log_buffer_lock:
                    current_logs = recent_logs
                
                # Only process logs that arrived AFTER this connection started
                new_logs = current_logs[initial_log_count:]
                
                # Find new logs by ID
                for log in new_logs:
                    if log.get('id') not in seen_log_ids:
                        yield f"data: {json.dumps(log)}\n\n"
                        seen_log_ids.add(log.get('id'))
                
                # Update the initial count to current count for next iteration
                initial_log_count = len(current_logs)
                
                # Keep seen IDs manageable
                if len(seen_log_ids) > 200:
                    # Keep only IDs from recent logs
                    recent_ids = {log.get('id') for log in current_logs[-100:]}
                    seen_log_ids = recent_ids
                    
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
    Clear the log buffer and centralized log file.
    """
    global recent_logs
    with log_buffer_lock:
        recent_logs.clear()
    
    # Clear the centralized log file
    centralized_logger.clear_logs()
    
    centralized_logger.log_info("Logs cleared by user", "SnapApi")
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
