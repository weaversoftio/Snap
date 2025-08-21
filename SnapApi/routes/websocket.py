from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect
import asyncio
from typing import Dict
from datetime import datetime, timedelta

active_connections: Dict[str, WebSocket] = {}

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
                print(f"Received Ping from {username}")

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
    # Get the current timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Check if 'message' key exists in the data dictionary
    if 'message' in data:
        # Prepend the timestamp to the message
        data['message'] = f"{timestamp} \n{data['message']}"

    if username in active_connections:
        try:
            await active_connections[username].send_json(data)  # Send the modified data
            return {"status": "success", "message": f"Sent to {username}"}
        except Exception as e:
            active_connections.pop(username, None)  # Remove disconnected users
            return {"status": "error", "message": f"Failed to send to {username}: {str(e)}"}
    
    print(f"Websocket {username} not found")

