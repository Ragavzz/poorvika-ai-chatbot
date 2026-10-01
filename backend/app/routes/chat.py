"""Chat API route handling AI shopping assistant conversations."""

import logging
import time
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.database.session import get_db

logger = logging.getLogger("shopai.routes.chat")

chat_router = APIRouter(prefix="/api", tags=["Chat"])


@chat_router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    """
    Handles customer conversational queries.
    Preserves exact contract with the React frontend Chatbot:
    Request:  POST /api/chat {"message": "..."}
    Response: {"response": "..."}
    """
    if not request.message or not request.message.strip():
        return ChatResponse(response="Please provide a message or question about what you're shopping for.")

    started = time.perf_counter()
    try:
        service = ChatService(db=db)
        return await service.generate_response(request)
    finally:
        logger.info("CHAT TIMING total_ms=%.1f", (time.perf_counter() - started) * 1000)
