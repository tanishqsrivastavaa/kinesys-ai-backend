"""
WebSocket Connection Manager for real-time call streaming.

Manages connections between AI agents and frontend clients,
enabling real-time message broadcasting for call sessions.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for real-time call streaming.

    Handles:
    - Frontend clients subscribing to specific call_ids
    - Agent connections broadcasting messages to frontends
    - Thread-safe connection management with asyncio locks
    - Graceful disconnection and cleanup
    """

    def __init__(self) -> None:
        # Map of call_id -> set of connected frontend WebSockets
        self._frontends: dict[str, set[WebSocket]] = {}
        # Lock for thread-safe operations on _frontends
        self._lock = asyncio.Lock()
        # Track active agent connection
        self._agent_ws: WebSocket | None = None

    async def connect_frontend(self, websocket: WebSocket, call_id: str) -> None:
        """
        Accept and register a frontend WebSocket connection for a specific call.

        Args:
            websocket: The WebSocket connection to register
            call_id: The call identifier to subscribe to
        """
        await websocket.accept()
        async with self._lock:
            if call_id not in self._frontends:
                self._frontends[call_id] = set()
            self._frontends[call_id].add(websocket)
        logger.info(f"Frontend connected to call {call_id}. Total frontends for call: {len(self._frontends[call_id])}")

    async def disconnect_frontend(self, websocket: WebSocket, call_id: str) -> None:
        """
        Remove a frontend WebSocket connection from a call.

        Args:
            websocket: The WebSocket connection to remove
            call_id: The call identifier to unsubscribe from
        """
        async with self._lock:
            if call_id in self._frontends:
                self._frontends[call_id].discard(websocket)
                # Clean up empty call entries
                if not self._frontends[call_id]:
                    del self._frontends[call_id]
                    logger.info(f"No more frontends for call {call_id}, cleaned up")
                else:
                    logger.info(f"Frontend disconnected from call {call_id}. Remaining: {len(self._frontends[call_id])}")

    async def connect_agent(self, websocket: WebSocket) -> None:
        """
        Accept an agent WebSocket connection.

        Args:
            websocket: The agent WebSocket connection
        """
        await websocket.accept()
        self._agent_ws = websocket
        logger.info("Agent connected")

    async def disconnect_agent(self) -> None:
        """Mark the agent as disconnected."""
        self._agent_ws = None
        logger.info("Agent disconnected")

    async def broadcast_to_call(self, call_id: str, message: str) -> int:
        """
        Broadcast a message to all frontends subscribed to a call.

        Args:
            call_id: The call identifier
            message: The raw message string to broadcast

        Returns:
            Number of frontends the message was successfully sent to
        """
        sent_count = 0
        failed_websockets: list[WebSocket] = []

        async with self._lock:
            frontends = self._frontends.get(call_id, set()).copy()

        for ws in frontends:
            try:
                await ws.send_text(message)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send message to frontend: {e}")
                failed_websockets.append(ws)

        # Clean up failed connections
        if failed_websockets:
            async with self._lock:
                if call_id in self._frontends:
                    for ws in failed_websockets:
                        self._frontends[call_id].discard(ws)

        return sent_count

    async def get_frontend_count(self, call_id: str) -> int:
        """Get the number of frontends connected to a specific call."""
        async with self._lock:
            return len(self._frontends.get(call_id, set()))

    async def get_active_calls(self) -> list[str]:
        """Get a list of all call_ids with active frontend connections."""
        async with self._lock:
            return list(self._frontends.keys())

    async def send_to_frontend(self, websocket: WebSocket, data: dict[str, Any]) -> bool:
        """
        Send a JSON message to a specific frontend.

        Args:
            websocket: The target WebSocket
            data: Dictionary to send as JSON

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            await websocket.send_json(data)
            return True
        except Exception as e:
            logger.warning(f"Failed to send to frontend: {e}")
            return False


# Singleton instance for use across the application
manager = ConnectionManager()
