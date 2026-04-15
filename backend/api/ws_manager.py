"""
WebSocket connection manager — broadcasts LangGraph cycle events to all connected frontend clients.
"""
import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)
        logger.info(f"WS client connected. Total: {len(self._connections)}")

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            if ws in self._connections:
                self._connections.remove(ws)
        logger.info(f"WS client disconnected. Total: {len(self._connections)}")

    async def broadcast(self, data: Any):
        """Broadcast JSON payload to all connected clients."""
        if not self._connections:
            return

        msg = json.dumps(data, default=str)
        dead: list[WebSocket] = []

        async with self._lock:
            for ws in self._connections:
                try:
                    await ws.send_text(msg)
                except Exception:
                    dead.append(ws)

        for ws in dead:
            await self.disconnect(ws)

    async def broadcast_event(self, event: dict):
        """Forward a LangGraph event to frontend."""
        event_type = event.get("event", "")
        if event_type in ("on_chain_start", "on_chain_stream", "on_chain_end"):
            node_name = event.get("name", "")
            data = event.get("data", {})
            await self.broadcast({
                "type": "graph_event",
                "node": node_name,
                "event": event_type,
                "data": data,
            })

    @property
    def connection_count(self) -> int:
        return len(self._connections)
