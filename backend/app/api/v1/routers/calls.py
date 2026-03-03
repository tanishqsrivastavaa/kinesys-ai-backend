"""
WebSocket endpoints for real-time call streaming.

Provides WebSocket connections for:
- AI Agents to stream call data
- Frontend clients to receive real-time updates for specific calls
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.services.websocket_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()
ws_router = APIRouter()  # Separate router for WebSocket routes (registered at root)


@ws_router.websocket("/ws/agent")
async def agent_websocket(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for AI Agent connections.

    The agent sends messages with the following structure:
    {
        "id": "call_id",
        "type": "transcript|event|status",
        "data": { ... }
    }

    Messages are broadcast to all frontends subscribed to the call_id.
    """
    await manager.connect_agent(websocket)

    try:
        while True:
            # Receive message from agent
            raw_data = await websocket.receive_text()

            try:
                message = json.loads(raw_data)
            except json.JSONDecodeError as e:
                logger.warning(f"Agent sent invalid JSON: {e}")
                await websocket.send_json({
                    "error": "Invalid JSON format",
                    "type": "error"
                })
                continue

            # Validate message structure
            call_id = message.get("id")
            if not call_id:
                logger.warning("Agent message missing 'id' field")
                await websocket.send_json({
                    "error": "Message must include 'id' field",
                    "type": "error"
                })
                continue

            # Broadcast to all frontends watching this call
            sent_count = await manager.broadcast_to_call(call_id, raw_data)
            logger.debug(f"Broadcast message for call {call_id} to {sent_count} frontends")

            # Optionally send acknowledgment to agent
            await websocket.send_json({
                "type": "ack",
                "call_id": call_id,
                "delivered_to": sent_count
            })

    except WebSocketDisconnect:
        logger.info("Agent disconnected normally")
    except Exception as e:
        logger.error(f"Agent WebSocket error: {e}")
    finally:
        await manager.disconnect_agent()


@ws_router.websocket("/ws/calls/{call_id}")
async def frontend_websocket(websocket: WebSocket, call_id: str) -> None:
    """
    WebSocket endpoint for Frontend clients to receive call updates.

    Clients connect to a specific call_id and receive all messages
    broadcast by the agent for that call.

    Path Parameters:
        call_id: The unique identifier for the call to subscribe to

    The frontend can also send messages (e.g., for ping/pong or commands):
    {
        "type": "ping|command",
        ...
    }
    """
    if not call_id or not call_id.strip():
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect_frontend(websocket, call_id)

    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "call_id": call_id,
            "message": f"Subscribed to call {call_id}"
        })

        while True:
            # Keep connection alive and handle any frontend messages
            raw_data = await websocket.receive_text()

            try:
                message = json.loads(raw_data)
            except json.JSONDecodeError:
                # Non-JSON messages (like simple pings) are acceptable
                continue

            msg_type = message.get("type", "")

            # Handle ping messages for keep-alive
            if msg_type == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "call_id": call_id
                })
            # Handle other frontend commands as needed
            elif msg_type == "status":
                frontend_count = await manager.get_frontend_count(call_id)
                await websocket.send_json({
                    "type": "status",
                    "call_id": call_id,
                    "connected_clients": frontend_count
                })

    except WebSocketDisconnect:
        logger.info(f"Frontend disconnected from call {call_id}")
    except Exception as e:
        logger.error(f"Frontend WebSocket error for call {call_id}: {e}")
    finally:
        await manager.disconnect_frontend(websocket, call_id)


@router.get("/active", tags=["calls"])
async def get_active_calls() -> dict[str, Any]:
    """
    Get a list of all active calls with connected frontends.

    Returns:
        Dictionary with list of active call_ids and count
    """
    active_calls = await manager.get_active_calls()
    return {
        "active_calls": active_calls,
        "count": len(active_calls)
    }


@router.get("/{call_id}/status", tags=["calls"])
async def get_call_status(call_id: str) -> dict[str, Any]:
    """
    Get the connection status for a specific call.

    Args:
        call_id: The call identifier

    Returns:
        Dictionary with connection count and status
    """
    frontend_count = await manager.get_frontend_count(call_id)
    return {
        "call_id": call_id,
        "connected_frontends": frontend_count,
        "active": frontend_count > 0
    }
