"""Isolated suggestion API with diagnostic Server-Timing and timestamp logs."""

import json
import logging
import time
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from app.schemas.suggestions import SuggestionRequest, SuggestionResponse
from app.services.ollama_service import OllamaService

logger = logging.getLogger("shopai.routes.suggestions")


class SuggestionTimingRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def timed(request: Request):
            started = time.perf_counter()
            timings = {"backend_received": datetime.now(timezone.utc).isoformat()}
            request.state.suggestion_timings = timings
            try:
                response = await handler(request)
            except HTTPException as exc:
                response = JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)
            timings["backend_api_ms"] = round((time.perf_counter() - started) * 1000, 3)
            response.headers["Server-Timing"] = f'suggestions;dur={timings["backend_api_ms"]}, ollama;dur={timings.get("ollama_ms", 0)}'
            response.headers["X-ShopAI-Suggestion-Timing"] = json.dumps(timings, separators=(",", ":"))
            response.headers["Access-Control-Expose-Headers"] = "Server-Timing, X-ShopAI-Suggestion-Timing"
            logger.info("[SUGGESTION TIMING] %s", json.dumps(timings, separators=(",", ":")))
            return response

        return timed


suggestions_router = APIRouter(prefix="/api/chat", tags=["Chat"], route_class=SuggestionTimingRoute)


@suggestions_router.post("/suggestions", response_model=SuggestionResponse)
def suggestions(request: SuggestionRequest, http_request: Request) -> SuggestionResponse:
    try:
        return OllamaService().generate_suggestions(
            request.product.model_dump(exclude_none=True),
            timings=http_request.state.suggestion_timings,
        )
    except Exception as exc:
        logger.warning("Suggestion generation failed: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Suggestions are unavailable") from exc
