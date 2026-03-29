"""Chat API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .deps import get_chat_service, get_stream_service
from ..services.chat_service import ChatService
from ..services.stream_service import StreamService


router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    """Chat request model."""
    query: str
    session_id: Optional[str] = "default"
    user_id: Optional[str] = "default_user"


class ChatResponse(BaseModel):
    """Chat response model."""
    answer: str
    citations: Optional[dict] = None
    session_id: str


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service)
):
    """Handle chat request."""
    try:
        # 使用 await 调用异步方法
        response = await chat_service.chat(
            query=request.query,
            session_id=request.session_id,
            user_id=request.user_id
        )
        return ChatResponse(
            answer=response.answer,
            citations=response.citations,
            session_id=response.session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    stream_service: StreamService = Depends(get_stream_service)
):
    """Handle streaming chat request."""
    from fastapi.responses import StreamingResponse
    
    async def generate():
        async for event in stream_service.stream_chat(
            query=request.query,
            session_id=request.session_id,
            user_id=request.user_id
        ):
            yield f"data: {event}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )
