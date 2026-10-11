"""Chat API route handling AI shopping assistant conversations."""

import logging
import json
import time
import re
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Response, Request, HTTPException
from sqlalchemy.orm import Session
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.database.session import get_db

logger = logging.getLogger("shopai.routes.chat")

chat_router = APIRouter(prefix="/api", tags=["Chat"])


@chat_router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, response: Response, http_request: Request, db: Session = Depends(get_db)) -> ChatResponse:
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
    incoming_id = http_request.headers.get('X-ShopAI-Request-ID', '')
    timings['request_id'] = incoming_id if re.fullmatch(r'[a-zA-Z0-9_-]{1,128}', incoming_id) else str(uuid.uuid4())
    failure = None
    service = None
    try:
        if not request.message or not request.message.strip():
            return ChatResponse(response="Please provide a message or question about what you're shopping for.")
        service = ChatService(db=db)
        result = await service.generate_response(request, timings=timings)
        result.response_source = service._response_source
        result.decision_provider = timings.get("decision_provider")
        timings["response_source"] = result.response_source
        return result
    except HTTPException as exc:
        failure = exc
        timings['http_status'] = exc.status_code
        timings['failure_reason'] = str(exc.detail)
        timings['response_source'] = getattr(service, '_response_source', 'request_error')
        raise
    finally:
        timings["response_total_ms"] = round((time.perf_counter() - started) * 1000, 1)
        headers = {
            'X-ShopAI-Request-ID': timings['request_id'],
            'X-ShopAI-Chat-Timing': json.dumps(timings, separators=(',', ':')),
            'Access-Control-Expose-Headers': 'X-ShopAI-Request-ID, X-ShopAI-Chat-Timing',
        }
        if failure is not None:
            failure.headers = {**(failure.headers or {}), **headers}
        else:
            response.headers.update(headers)
        logger.info("[TIMING] %s", json.dumps(timings, separators=(",", ":")))
