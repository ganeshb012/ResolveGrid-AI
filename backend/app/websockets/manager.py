import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import WebSocket

logger = logging.getLogger("resolvegrid.websocket")


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts real-time events."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.user_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: Optional[str] = None):
        await websocket.accept()
        self.active_connections.append(websocket)
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
            self.user_connections[user_id].append(websocket)
        logger.info("WebSocket connected. Active total: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket, user_id: Optional[str] = None):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if user_id and user_id in self.user_connections:
            if websocket in self.user_connections[user_id]:
                self.user_connections[user_id].remove(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        logger.info("WebSocket disconnected. Active total: %d", len(self.active_connections))

    async def broadcast(self, event_type: str, data: Dict[str, Any]):
        """Broadcast event to all connected clients."""
        payload = json.dumps({"event": event_type, "data": data})
        stale_connections = []

        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.warning("Error broadcasting to connection: %s", str(e))
                stale_connections.append(connection)

        for stale in stale_connections:
            self.disconnect(stale)

    async def send_to_user(self, user_id: str, event_type: str, data: Dict[str, Any]):
        """Send event directly to a specific user's active sockets."""
        if user_id not in self.user_connections:
            return

        payload = json.dumps({"event": event_type, "data": data})
        stale_connections = []

        for connection in self.user_connections[user_id]:
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.warning("Error sending to user %s: %s", user_id, str(e))
                stale_connections.append(connection)

        for stale in stale_connections:
            self.disconnect(stale, user_id)


ws_manager = ConnectionManager()
