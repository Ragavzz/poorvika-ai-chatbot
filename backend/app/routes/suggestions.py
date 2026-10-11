"""Isolated suggestion API with diagnostic Server-Timing and timestamp logs."""

import json
import logging
import time
import re
import uuid
import requests
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from app.config import settings
from app.schemas.suggestions import SuggestionRequest, SuggestionResponse
from app.services.suggestion_service import generate_suggestions, configuration_key

logger = logging.getLogger("shopai.routes.suggestions")


class SuggestionTimingRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def timed(request: Request):
            started = time.perf_counter()
            supplied_id = request.headers.get('X-ShopAI-Request-ID', '')
            request_id = supplied_id if re.fullmatch(r'[a-zA-Z0-9_-]{1,128}', supplied_id) else str(uuid.uuid4())
            timings = {"request_id": request_id, "backend_received": datetime.now(timezone.utc).isoformat(), "laya_ms": 0, "laya_call_count": 0, "ollama_call_count": 0}
            request.state.suggestion_timings = timings
            try:
                response = await handler(request)
            except HTTPException as exc:
                response = JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)
            timings["backend_api_ms"] = round((time.perf_counter() - started) * 1000, 3)
            timings['status'] = response.status_code
            response.headers['X-ShopAI-Request-ID'] = request_id
            response.headers["Server-Timing"] = f'suggestions;dur={timings["backend_api_ms"]}, ollama;dur={timings.get("ollama_ms", 0)}'
            response.headers["X-ShopAI-Suggestion-Timing"] = json.dumps(timings, separators=(",", ":"))
            response.headers["Access-Control-Expose-Headers"] = "Server-Timing, X-ShopAI-Suggestion-Timing, X-ShopAI-Request-ID"
            logger.info("[SUGGESTION TIMING] %s", json.dumps(timings, separators=(",", ":")))
            return response

        return timed


suggestions_router = APIRouter(prefix="/api/chat", tags=["Chat"], route_class=SuggestionTimingRoute)


@suggestions_router.get('/suggestion-capabilities')
def suggestion_capabilities():
    return {'ollama_enabled': settings.OLLAMA_ENABLED, 'model_configuration': configuration_key(),
            'timeout_ms': (settings.SUGGESTION_TIMEOUT_SECONDS + 8) * 1000}


@suggestions_router.post("/suggestions", response_model=SuggestionResponse)
def suggestions(request: SuggestionRequest, http_request: Request) -> SuggestionResponse:
    if not settings.OLLAMA_ENABLED:
        raise HTTPException(status_code=503, detail="Response generation is disabled by configuration.")
    try:
        return generate_suggestions(
            request.product.model_dump(exclude_none=True),
            timings=http_request.state.suggestion_timings,
        )
    except Exception as exc:
        timeout = isinstance(exc, (requests.Timeout, TimeoutError))
        reason = 'timeout' if timeout else 'invalid_model_output' if isinstance(exc, ValueError) else 'model_connection_or_service_failure'
        http_request.state.suggestion_timings['failure_reason'] = reason
        logger.exception("Suggestion generation failed request_id=%s reason=%s type=%s", http_request.state.suggestion_timings['request_id'], reason, type(exc).__name__)
        raise HTTPException(status_code=504 if timeout else 503, detail=f"Suggestions are unavailable ({reason}).") from exc
