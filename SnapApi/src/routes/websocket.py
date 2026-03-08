from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect
import asyncio
from typing import Dict
from datetime import datetime
import logging
import uuid

active_connections: Dict[str, WebSocket] = {}
logger = logging.getLogger("automation_api")

router = APIRouter()

@router.websocket("/progress/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    """Handles WebSocket connection and listens for pings."""
    await websocket.accept()
    active_connections[username] = websocket
    print(f"User {username} connected")


    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                pass  # Ping received, no logging needed

                await websocket.send_json({"type": "pong"})
            else:
                print(f"Received from {username}: {data}")

    except WebSocketDisconnect as e:
        print(f"User {username} got disconnected")
    finally:
        active_connections.pop(username, None)

async def disconnect(username: str):
    try:
        active_connections.pop(username, None)
    except Exception as e:
        print("error disconnecting", str(e))

        # print(f"User {username} disconnected.")

async def send_progress(username: str, data: dict):
    """Send a message to a specific user if they are connected."""
    data["type"] = "progress"
    # Add timestamp to the data structure (not to the message)
    data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Mirror progress messages into the SSE logs buffer used by the Logs UI.
    try:
        from routes.logs import add_log_to_buffer

        progress_value = data.get("progress")
        log_type = "info"
        if progress_value == "failed":
            log_type = "error"
        elif progress_value == 100:
            log_type = "success"

        add_log_to_buffer({
            "id": str(uuid.uuid4()),
            "timestamp": data["timestamp"],
            "message": data.get("message", ""),
            "type": log_type,
            "level": log_type,
            "initiator": data.get("initiator", "SnapApi"),
            "task_name": data.get("task_name", "General Operation"),
        })
    except Exception as e:
        logger.warning(f"Failed to mirror progress message to log buffer: {str(e)}")

    if username in active_connections:
        try:
            await active_connections[username].send_json(data)  # Send the modified data
            return {"status": "success", "message": f"Sent to {username}"}
        except Exception as e:
            active_connections.pop(username, None)  # Remove disconnected users
            logger.warning(f"Failed to send progress to {username}: {str(e)}")
            return {"status": "error", "message": f"Failed to send to {username}: {str(e)}"}
    
    # Keep backend visibility when socket client is not connected.
    logger.info(f"Progress recipient {username} not connected; message: {data.get('message', '')}")
    return {"status": "error", "message": f"User {username} not connected"}

async def broadcast_progress(data: dict):
    """Send a message to all connected users."""
    data["type"] = "progress"
    # Add timestamp to the data structure (not to the message)
    data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Send to all connected users
    disconnected_users = []
    for username, websocket in active_connections.items():
        try:
            await websocket.send_json(data)
        except Exception as e:
            print(f"SnapAPI: Failed to send to {username}: {str(e)}")
            disconnected_users.append(username)
    
    # Remove disconnected users
    for username in disconnected_users:
        active_connections.pop(username, None)
    
    return {"status": "success", "message": f"Broadcasted to {len(active_connections)} users"}

