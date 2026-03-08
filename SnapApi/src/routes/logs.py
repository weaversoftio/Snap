"""
Logs API endpoint for SnapApi
Streams logs to the UI via in-memory buffer and Server-Sent Events
"""

import asyncio
import json
import logging
import sys
import io
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import threading

from middleware.verify_token import verify_token

router = APIRouter()
logger = logging.getLogger("automation_api")

# Pydantic models for notifications
class NotificationRequest(BaseModel):
    """Model for sending notifications to the web UI."""
    message: str
    level: str = "info"  # info, success, warning, error, debug
    initiator: str = "SnapApi"
    show_in_ui: bool = True
    title: Optional[str] = None  # Optional notification title
    category: Optional[str] = None  # Optional category for grouping notifications


class NotificationResponse(BaseModel):
    """Response model for notification requests."""
    status: str
    message: str
    notification_id: str

# Store recent logs in memory (circular buffer)
MAX_LOG_ENTRIES = 1000
recent_logs: List[Dict[str, Any]] = []
log_buffer_lock = threading.Lock()
# Track recent log content hashes to prevent duplicates (within 1 second window)
recent_log_hashes: set = set()
recent_log_hashes_timestamps: Dict[str, float] = {}

def add_log_to_buffer(log_entry: Dict[str, Any]):
    """Add a log entry to the circular buffer, avoiding duplicates."""
    global recent_logs, recent_log_hashes, recent_log_hashes_timestamps
    import time
    
    with log_buffer_lock:
        # Create a content hash for duplicate detection (message + timestamp + initiator)
        # Use timestamp with 1 second precision to catch duplicates within the same second
        timestamp_rounded = log_entry.get('timestamp', '')[:16]  # Round to nearest second (YYYY-MM-DD HH:MM:SS)
        content_hash = f"{log_entry.get('message', '')}-{timestamp_rounded}-{log_entry.get('initiator', 'unknown')}"
        current_time = time.time()
        
        # Check if this exact log was added recently (within last 2 seconds)
        if content_hash in recent_log_hashes:
            hash_timestamp = recent_log_hashes_timestamps.get(content_hash, 0)
            if current_time - hash_timestamp < 2.0:  # Within 2 seconds
                # Duplicate detected, skip adding
                return
        
        # Add to buffer
        recent_logs.append(log_entry)
        
        # Track this hash
        recent_log_hashes.add(content_hash)
        recent_log_hashes_timestamps[content_hash] = current_time
        
        # Clean up old hashes (older than 10 seconds)
        cutoff_time = current_time - 10.0
        old_hashes = [h for h, ts in recent_log_hashes_timestamps.items() if ts < cutoff_time]
        for old_hash in old_hashes:
            recent_log_hashes.discard(old_hash)
            recent_log_hashes_timestamps.pop(old_hash, None)
        
        # Keep only the most recent entries
        if len(recent_logs) > MAX_LOG_ENTRIES:
            recent_logs = recent_logs[-MAX_LOG_ENTRIES:]



@router.get("/container")
async def get_container_logs(username: str = Depends(verify_token)):
    """
    Get SnapApi logs from in-memory buffer.
    Returns logs from the in-memory logging buffer.
    """
    try:
        # Get logs from memory buffer only (for real-time updates)
        with log_buffer_lock:
            logs_to_return = recent_logs[-100:]  # Get last 100 logs
        
        return {
            "logs": logs_to_return,
            "source": "memory_buffer",
            "total_lines": len(logs_to_return)
        }
        
    except Exception as e:
        logger.error(f"Failed to get logs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get logs: {str(e)}"
        )

@router.get("/stream")
async def stream_logs(request: Request):
    """Stream logs using Server-Sent Events (SSE)."""
    try:
        # Try to get token from cookie first (preferred method)
        token = request.cookies.get("token")
        
        # Fallback to query parameter for backward compatibility
        # (in case frontend hasn't reloaded yet)
        if not token:
            token = request.query_params.get("token")
        
        if not token:
            raise HTTPException(status_code=401, detail="Missing authentication token")
        
        # Check if this is a Kubernetes service account token
        from middleware.verify_token import _is_kubernetes_service_account_token
        if _is_kubernetes_service_account_token(token):
            username = "system:serviceaccount"
        else:
            # Handle regular JWT tokens for users
            from flows.config.user.verify_user_config import verify_user_config
            result = verify_user_config(token)
            if result.get("success") == False:
                raise HTTPException(status_code=401, detail="Invalid or Expired token")
            username = result["user"]["username"]
        
        async def event_generator():
            try:
                # Send existing logs first when connection is established
                with log_buffer_lock:
                    existing_logs = recent_logs[-50:]  # Send last 50 existing logs
                    last_log_count = len(recent_logs)
                
                # Send existing logs
                for log in existing_logs:
                    try:
                        log_str = json.dumps(log)
                        yield f"data: {log_str}\n\n"
                    except Exception as e:
                        continue
                
                # Then stream new logs
                while True:
                    try:
                        payloads = []
                        with log_buffer_lock:
                            current_log_count = len(recent_logs)
                            
                            if current_log_count > last_log_count:
                                # New logs available
                                new_logs = recent_logs[last_log_count:]
                                last_log_count = current_log_count

                                for log in new_logs:
                                    try:
                                        payloads.append(f"data: {json.dumps(log)}\n\n")
                                    except Exception:
                                        continue
                            else:
                                # No new logs, send keep-alive
                                payloads.append(f"data: {json.dumps({'type': 'keepalive', 'timestamp': datetime.now().isoformat()})}\n\n")

                        # Never yield while holding log_buffer_lock.
                        for payload in payloads:
                            yield payload
                        
                        await asyncio.sleep(1)  # Check every second
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        break
            except Exception as e:
                import traceback
                traceback.print_exc()
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
                "X-Accel-Buffering": "no"  # Disable buffering in nginx if present
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

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
            "total": len(recent_logs),
            "buffer_size": len(recent_logs)
        }

@router.get("/test")
async def test_logs(username: str = Depends(verify_token)):
    """
    Test endpoint to add a log and verify the system is working.
    """
    test_log_entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "message": "Test log message from /logs/test endpoint",
        "type": "info",
        "level": "info",
        "initiator": "SnapApi"
    }
    add_log_to_buffer(test_log_entry)
    logger.info("Test log added via /logs/test endpoint")
    
    with log_buffer_lock:
        return {
            "status": "success",
            "message": "Test log added",
            "test_log": test_log_entry,
            "buffer_size": len(recent_logs),
            "recent_logs_count": len(recent_logs)
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
    
    logger.info("Logs cleared by user")
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

@router.post("/notify", response_model=NotificationResponse)
async def send_notification(
    request: NotificationRequest, 
    username: str = Depends(verify_token)
):
    """
    Send a notification to the web UI.
    
    This endpoint allows sending notifications that will appear in the web UI
    and be logged to the standard logging system.
    
    Args:
        request: Notification details including message, level, and metadata
        username: Authenticated username (from token verification)
    
    Returns:
        NotificationResponse with status and notification ID
    """
    try:
        # Validate level
        valid_levels = ["info", "success", "warning", "error", "debug"]
        if request.level not in valid_levels:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid level '{request.level}'. Must be one of: {', '.join(valid_levels)}"
            )
        
        # Generate notification ID
        notification_id = str(uuid.uuid4())
        
        # Create the notification message
        notification_message = request.message
        if request.title:
            notification_message = f"{request.title}: {request.message}"
        
        # Add category if provided
        if request.category:
            notification_message = f"[{request.category}] {notification_message}"
        
        # Log to standard logging system
        if request.level == "error":
            logger.error(f"[{request.initiator}] {notification_message}")
        elif request.level == "warning":
            logger.warning(f"[{request.initiator}] {notification_message}")
        elif request.level == "debug":
            logger.debug(f"[{request.initiator}] {notification_message}")
        else:  # info or success
            logger.info(f"[{request.initiator}] {notification_message}")
        
        # Add to UI buffer if show_in_ui is True
        if request.show_in_ui:
            log_entry = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "message": notification_message,
                "level": request.level,
                "initiator": request.initiator,
                "raw_line": notification_message
            }
            add_log_to_buffer(log_entry)
        
        # Log the notification request for audit purposes
        logger.info(f"Notification sent by user '{username}': {request.message}")
        
        return NotificationResponse(
            status="success",
            message="Notification sent successfully",
            notification_id=notification_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send notification: {str(e)}"
        )
