"""
Enhanced WebSocket connection manager with heartbeat and better error handling
"""

import asyncio
import logging
from typing import List, Optional, Dict
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

logger = logging.getLogger(__name__)


class WsConnectionMetadata:
    """Metadata about a WebSocket connection"""
    def __init__(self):
        self.connected_at = datetime.utcnow()
        self.last_heartbeat = datetime.utcnow()
        self.message_count = 0
        self.bytes_sent = 0
        self.bytes_received = 0


class ConnectionManager:
    """
    Manages WebSocket connections with heartbeat, reconnection tracking,
    and dead connection cleanup.
    """

    def __init__(self, heartbeat_interval: int = 30):
        self.active_connections: List[WebSocket] = []
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_task: Optional[asyncio.Task] = None
        self._metadata: Dict[int, WsConnectionMetadata] = {}

    async def connect(self, ws: WebSocket) -> None:
        """Accept and register a WebSocket connection"""
        await ws.accept()
        self.active_connections.append(ws)
        self._metadata[id(ws)] = WsConnectionMetadata()
        logger.info(
            f"✅ WebSocket connected",
            extra={"total_connections": len(self.active_connections)}
        )

    def disconnect(self, ws: WebSocket) -> None:
        """Remove a WebSocket connection safely"""
        if ws in self.active_connections:
            self.active_connections.remove(ws)
            self._metadata.pop(id(ws), None)
            logger.info(
                f"🔌 WebSocket disconnected",
                extra={"remaining_connections": len(self.active_connections)}
            )

    async def broadcast(self, data: dict) -> int:
        """
        Send data to all connected clients.
        Returns number of successful sends.
        """
        dead_connections = []
        success_count = 0

        for ws in self.active_connections.copy():
            try:
                await ws.send_json(data)
                success_count += 1

                # Update metadata
                meta = self._metadata.get(id(ws))
                if meta:
                    meta.last_heartbeat = datetime.utcnow()
                    meta.bytes_sent += len(str(data))

            except Exception as e:
                logger.warning(
                    f"Failed to send to client: {e}",
                    extra={"error_type": type(e).__name__}
                )
                dead_connections.append(ws)

        # Clean up dead connections
        for ws in dead_connections:
            self.disconnect(ws)

        return success_count
    
    async def handle_message(self, ws: WebSocket, data: dict) -> None:
        """
        Handle incoming WebSocket messages (ping/pong, commands, etc.)
        
        Args:
            ws: WebSocket connection that sent the message
            data: Parsed JSON message
        """
        message_type = data.get("type", "").lower()
        
        # Handle heartbeat ping from client
        if message_type == "ping":
            logger.debug("📡 Received ping, sending pong")
            try:
                await ws.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat(),
                })
                
                # Update last heartbeat
                meta = self._metadata.get(id(ws))
                if meta:
                    meta.last_heartbeat = datetime.utcnow()
                    
            except Exception as e:
                logger.warning(f"Failed to send pong: {e}")
                self.disconnect(ws)
        
        # Handle pong response (if we sent ping)
        elif message_type == "pong":
            logger.debug("✅ Received pong")
            meta = self._metadata.get(id(ws))
            if meta:
                meta.last_heartbeat = datetime.utcnow()
        
        # Other message types can be handled by caller
        else:
            logger.debug(f"Received message type: {message_type}")
            meta = self._metadata.get(id(ws))
            if meta:
                meta.message_count += 1
                meta.bytes_received += len(str(data))

    async def broadcast_exclusive(self, ws: WebSocket, data: dict) -> bool:
        """Send to a specific connection"""
        try:
            await ws.send_json(data)

            meta = self._metadata.get(id(ws))
            if meta:
                meta.bytes_sent += len(str(data))

            return True

        except Exception as e:
            logger.error(f"Failed to send exclusive: {e}")
            self.disconnect(ws)
            return False

    async def send_heartbeat(self) -> None:
        """Periodically send heartbeat to detect dead clients"""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                await self.broadcast({
                    "type": "heartbeat",
                    "timestamp": datetime.utcnow().isoformat(),
                })
            except Exception as e:
                logger.error(f"Heartbeat error: {e}", exc_info=True)

    async def start_heartbeat(self) -> None:
        """Start the heartbeat task"""
        if not self.heartbeat_task or self.heartbeat_task.done():
            self.heartbeat_task = asyncio.create_task(self.send_heartbeat())
            logger.info("❤️ WebSocket heartbeat started")

    def stop_heartbeat(self) -> None:
        """Stop the heartbeat task"""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            logger.info("⏹️ WebSocket heartbeat stopped")

    def get_stats(self) -> dict:
        """Statistics about active connections"""
        if not self.active_connections:
            return {
                "active_connections": 0,
                "avg_uptime_seconds": 0,
                "total_messages": 0,
                "total_bytes_sent": 0,
            }

        now = datetime.utcnow()
        uptimes = [
            (now - meta.connected_at).total_seconds()
            for meta in self._metadata.values()
        ]
        message_counts = [meta.message_count for meta in self._metadata.values()]
        bytes_sent = [meta.bytes_sent for meta in self._metadata.values()]

        return {
            "active_connections": len(self.active_connections),
            "avg_uptime_seconds": sum(uptimes) / len(uptimes) if uptimes else 0,
            "total_messages": sum(message_counts),
            "total_bytes_sent": sum(bytes_sent),
        }

    def close_all(self) -> None:
        """Close all connections (shutdown)"""
        for ws in self.active_connections.copy():
            try:
                asyncio.create_task(ws.close())
            except Exception:
                pass
        self.active_connections.clear()
        self._metadata.clear()
        logger.info("✅ All WebSocket connections closed")
