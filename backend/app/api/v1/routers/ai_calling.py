"""
AI Calling endpoints for LiveKit agent dispatch.

Provides endpoints for:
- Dispatching AI agents with dynamic configuration
- Creating rooms for calls
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from livekit import api

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Schemas
class AgentConfig(BaseModel):
    """Configuration for dispatching an AI agent."""
    phone_number: Optional[str] = Field(None, description="Phone number for the call")
    system_prompt: Optional[str] = Field(None, description="System prompt for the AI agent")
    welcome_message: Optional[str] = Field(None, description="Welcome message to greet the user")
    ai_speaks_first: bool = Field(True, description="Whether the AI should speak first")
    voice_id: Optional[str] = Field(None, description="Voice ID for TTS")
    llm_model: str = Field("gpt-4o-mini", description="LLM model to use")
    stt_model: str = Field("nova-3", description="STT model to use")
    style_guardrails: Optional[str] = Field(None, description="Style guardrails for the agent")


class DispatchRequest(BaseModel):
    """Request body for dispatching an agent."""
    agent_config: AgentConfig
    room_name: Optional[str] = Field(None, description="Optional room name. If not provided, one will be generated.")


class DispatchResponse(BaseModel):
    """Response after dispatching an agent."""
    success: bool
    room_name: str
    message: str


class RoomTokenRequest(BaseModel):
    """Request body for generating a room token."""
    room_name: str
    participant_name: str = Field(..., description="Name of the participant joining the room")


class RoomTokenResponse(BaseModel):
    """Response with room token for client connection."""
    token: str
    room_name: str
    livekit_url: str


async def dispatch_agent_with_config(agent_config: AgentConfig, room_name: str) -> None:
    """Dispatch agent with dynamic configuration."""
    lk_api = api.LiveKitAPI(
        url=settings.LIVEKIT_URL,
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET,
    )
    
    # Build metadata with all configurable fields
    metadata = json.dumps({
        "phone_number": agent_config.phone_number,
        "system_prompt": agent_config.system_prompt,
        "welcome_message": agent_config.welcome_message,
        "ai_speaks_first": agent_config.ai_speaks_first,
        "voice_id": agent_config.voice_id,
        "llm_model": agent_config.llm_model,
        "stt_model": agent_config.stt_model,
        "style_guardrails": agent_config.style_guardrails,
    })
    
    await lk_api.agent_dispatch.create_dispatch(
        api.CreateAgentDispatchRequest(
            agent_name=settings.LIVEKIT_AGENT_NAME,
            room=room_name,
            metadata=metadata,
        )
    )
    
    await lk_api.aclose()


@router.post("/dispatch", response_model=DispatchResponse, tags=["ai-calling"])
async def dispatch_agent(request: DispatchRequest) -> DispatchResponse:
    """
    Dispatch an AI agent to a room with the specified configuration.
    
    This endpoint creates a room (if needed) and dispatches an AI agent
    with the provided configuration.
    """
    try:
        # Generate room name if not provided
        room_name = request.room_name or f"call-{uuid.uuid4().hex[:12]}"
        
        # Create the room first
        lk_api = api.LiveKitAPI(
            url=settings.LIVEKIT_URL,
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )
        
        # Create room
        await lk_api.room.create_room(
            api.CreateRoomRequest(name=room_name)
        )
        
        await lk_api.aclose()
        
        # Dispatch the agent
        await dispatch_agent_with_config(request.agent_config, room_name)
        
        logger.info(f"Successfully dispatched agent to room: {room_name}")
        
        return DispatchResponse(
            success=True,
            room_name=room_name,
            message=f"Agent dispatched successfully to room {room_name}"
        )
        
    except Exception as e:
        logger.error(f"Failed to dispatch agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to dispatch agent: {str(e)}"
        )


@router.post("/token", response_model=RoomTokenResponse, tags=["ai-calling"])
async def get_room_token(request: RoomTokenRequest) -> RoomTokenResponse:
    """
    Generate a token for a participant to join a LiveKit room.
    
    This token allows clients to connect to the LiveKit room.
    """
    try:
        token = api.AccessToken(
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )
        
        token.with_identity(request.participant_name)
        token.with_name(request.participant_name)
        token.with_grants(api.VideoGrants(
            room_join=True,
            room=request.room_name,
        ))
        
        jwt_token = token.to_jwt()
        
        return RoomTokenResponse(
            token=jwt_token,
            room_name=request.room_name,
            livekit_url=settings.LIVEKIT_URL,
        )
        
    except Exception as e:
        logger.error(f"Failed to generate token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate token: {str(e)}"
        )


@router.get("/rooms", tags=["ai-calling"])
async def list_rooms() -> dict[str, Any]:
    """
    List all active LiveKit rooms.
    """
    try:
        lk_api = api.LiveKitAPI(
            url=settings.LIVEKIT_URL,
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )
        
        rooms = await lk_api.room.list_rooms(api.ListRoomsRequest())
        await lk_api.aclose()
        
        return {
            "rooms": [{"name": room.name, "num_participants": room.num_participants} for room in rooms.rooms],
            "count": len(rooms.rooms)
        }
        
    except Exception as e:
        logger.error(f"Failed to list rooms: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list rooms: {str(e)}"
        )
