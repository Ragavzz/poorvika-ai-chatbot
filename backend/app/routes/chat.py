"""Chat API route handling AI shopping assistant conversations."""

import logging
import json
import time
from datetime import datetime, timezone
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
    started = time.perf_counter()
    timings = {
        "request_received": datetime.now(timezone.utc).isoformat(),
        "laya_start": None, "laya_end": None, "laya_duration_ms": None,
        "laya_call_count": 0,
        "product_search_start": None, "product_search_end": None,
        "product_search_duration_ms": None, "postgres_query_duration_ms": None,
        "postgres_query_start": None, "postgres_query_end": None, "postgres_query_count": 0,
        "ollama_start": None, "ollama_end": None, "ollama_duration_ms": None,
        "ollama_http_duration_ms": None, "ollama_client_overhead_ms": None,
        "ollama_server_total_ms": None, "ollama_prompt_build_ms": None,
        "ollama_model_load_ms": None, "ollama_prompt_eval_ms": None,
        "ollama_generation_ms": None, "ollama_prompt_chars": None,
        "ollama_call_count": 0, "ollama_skipped_reason": None,
    }
    try:
        if not request.message or not request.message.strip():
            return ChatResponse(response="Please provide a message or question about what you're shopping for.")
        service = ChatService(db=db)
        return await service.generate_response(request, timings=timings)
    finally:
        timings["response_total_ms"] = round((time.perf_counter() - started) * 1000, 1)
        logger.info("[TIMING] %s", json.dumps(timings, separators=(",", ":")))
