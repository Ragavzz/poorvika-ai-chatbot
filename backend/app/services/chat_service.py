"""Chat orchestration: Laya decision, catalog/cart operation, then Ollama response."""

import json
import logging
import re
import time
from typing import Any, Dict, Tuple

from sqlalchemy.orm import Session

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.laya_client import LayaClient
from app.services.llm_service import LLMService
from app.services.ollama_service import OllamaService
from app.tools.product_search_tool import ProductSearchTool

logger = logging.getLogger("shopai.services.chat")
CLIENT_CONTEXT_RE = re.compile(r"\n\n<shopai_client_context>(.*?)</shopai_client_context>\s*$", re.S)
LOW_CONFIDENCE = 0.15


class ChatService:
    """Route each request through Laya, business data, and local Ollama."""

    def __init__(self, db: Session):
        self.db = db
        self.laya = LayaClient()
        self.ollama = OllamaService()
        self.search_tool = ProductSearchTool(db=db)
        self._response_source = "fallback"

    @staticmethod
    def _request_context(message: str) -> Tuple[str, Dict[str, Any]]:
        match = CLIENT_CONTEXT_RE.search(message)
        if not match:
            return message.strip(), {}
        try:
            context = json.loads(match.group(1))
        except json.JSONDecodeError:
            context = {}
        return message[: match.start()].strip(), context if isinstance(context, dict) else {}

    def _filters(self, message: str) -> Dict[str, Any]:
        # Laya selects the action. This small catalog vocabulary parser only extracts
        # filter values after that decision; it does not classify intent.
        parsed = LLMService._rule_based_intent_extraction(message)
        lowered = message.lower()
        # The bundled catalog distinguishes smartphones from headphones/accessories.
        if re.search(r"\b(?:iphone|smartphones?|phones?|mobiles?|cell ?phones?)\b", lowered):
            parsed["category"] = "Smartphones"
        if re.search(r"\biphone\b", lowered):
            parsed["brand"] = "Apple"

        around = re.search(r"(?:around|about|approximately|budget(?:\s+of)?|\bfor\b)\D{0,8}(\d[\d,]*(?:\.\d+)?)\s*(k)?\b", lowered)
        under = re.search(r"(?:under|below|less than|within)\D{0,8}(\d[\d,]*(?:\.\d+)?)\s*(k)?\b", lowered)
        above = re.search(r"(?:above|more than|over)\D{0,8}(\d[\d,]*(?:\.\d+)?)\s*(k)?\b", lowered)
        amount = around or under or above
        if amount:
            value = float(amount.group(1).replace(",", ""))
            value *= 1000 if amount.group(2) else 1
            if around:
                parsed["min_price"], parsed["max_price"] = value * 0.9, value * 1.1
            elif under:
                parsed["max_price"] = value
            else:
                parsed["min_price"] = value
        if parsed.get("category") or parsed.get("brand"):
            ignored = {
                "show", "me", "find", "suggest", "recommend", "a", "an", "the", "good",
                "best", "phone", "phones", "smartphone", "smartphones", "mobile", "mobiles",
                "cell", "under", "below", "less", "than", "within", "around", "about",
                "approximately", "budget", "of", "for", "over", "above", "more", "inr", "rs",
                "apple", "samsung", "sony", "philips", "mi",
            }
            qualifiers = [
                token for token in re.findall(r"[a-z0-9]+", lowered)
                if token not in ignored and not token.isdigit() and token != "k"
            ]
            parsed["search_term"] = " ".join(qualifiers) or None
        return parsed

    def _catalog_context(self, products: list, **extra: Any) -> Dict[str, Any]:
        return {**self.ollama.product_context(products), **extra}

    def _ollama_answer(self, message: str, context: Dict[str, Any]) -> str:
        try:
            logger.info("[AI FLOW] OLLAMA CALL: model=%s, url=%s", self.ollama.model, self.ollama.url)
            answer = self.ollama.generate(message, context)
            self._response_source = "ollama"
            logger.info("[AI FLOW] OLLAMA RESPONSE RECEIVED")
            return answer
        except Exception:
            self._response_source = "fallback"
            logger.info("[AI FLOW] OLLAMA FAILED - USING FALLBACK")
            logger.exception("OLLAMA generation failed")
            products = context.get("products") or []
            if products:
                # Keep the catalog available if local inference is temporarily down.
                return LLMService._format_products_markdown(message, products)
            return (
                "I couldn't reach the local Ollama model to prepare a response. "
                "Start it with `ollama serve`, then retry your message."
            )

    async def generate_response(self, request: ChatRequest) -> ChatResponse:
        full_message = (request.message or "").strip()
        user_message, client_context = self._request_context(full_message)
        if not user_message:
            return ChatResponse(response="Please provide a message or question about what you're shopping for.")

        # Laya must be the first decision step. Never fall back to a regex intent guess.
        laya_started = time.perf_counter()
        try:
            decision = self.laya.decide(user_message)
        except Exception:
            logger.info("CHAT TIMING laya_ms=%.1f", (time.perf_counter() - laya_started) * 1000)
            logger.exception("LAYA decision failed")
            return ChatResponse(
                response="I couldn't reach the Laya decision service. Start it on port 5055 and try again."
            )
        logger.info("CHAT TIMING laya_ms=%.1f", (time.perf_counter() - laya_started) * 1000)

        action = decision["choice"]
        confidence = decision.get("confidence")
        logger.info(
            "[AI FLOW] LAYA DECISION: choice=%s, confidence=%s, source=%s",
            action, confidence, decision.get("source"),
        )
        logger.info("DECISION action=%s confidence=%s", action, confidence)
        if isinstance(confidence, (int, float)) and confidence < LOW_CONFIDENCE:
            logger.info("LOW CONFIDENCE: asking for clarification without executing an action")
            return ChatResponse(response="I’m not sure which action you meant. Could you rephrase what you’d like me to do?")

        logger.info("TOOL/DATABASE action=%s", action)
        if action in ("product_search", "recommendation"):
            extraction_started = time.perf_counter()
            filters = self._filters(user_message)
            logger.info("CHAT TIMING product_filter_extraction_ms=%.1f filters=%s", (time.perf_counter() - extraction_started) * 1000, filters)
            db_started = time.perf_counter()
            products = self.search_tool.search_products(
                query=filters.get("search_term"),
                category=filters.get("category"),
                brand=filters.get("brand"),
                min_price=filters.get("min_price"),
                max_price=filters.get("max_price"),
                sort_by="rating" if action == "recommendation" else None,
                limit=5,
            )
            logger.info("CHAT TIMING postgres_query_ms=%.1f", (time.perf_counter() - db_started) * 1000)
            logger.info("TOOL/DATABASE returned %d products", len(products))
            logger.info("[AI FLOW] PRODUCT TOOL: %d products found", len(products))
            if not products:
                return ChatResponse(
                    response="I couldn't find products matching that request in the current catalog. Try a different brand, product type, or budget."
                )
            # The query has already been applied in PostgreSQL. Pass only the
            # matched product rows to the answer model, without redundant filters.
            context = self._catalog_context(products)
            generation_started = time.perf_counter()
            response = self._ollama_answer(user_message, context)
            logger.info("CHAT TIMING final_response_generation_ms=%.1f", (time.perf_counter() - generation_started) * 1000)
            if products:
                ids = [str(product["id"]) for product in products]
                response += f"\n\n[[SHOPAI_PRODUCTS:{','.join(ids)}]]"
            logger.info("[AI FLOW] FINAL RESPONSE: source=%s", self._response_source)
            return ChatResponse(response=response)

        if action == "product_details":
            ids = client_context.get("recent_product_ids") or []
            product = self.search_tool.get_product_by_id(str(ids[0])) if ids else None
            if not product:
                filters = self._filters(user_message)
                matches = self.search_tool.search_products(
                    query=filters.get("search_term"), brand=filters.get("brand"),
                    category=filters.get("category"), limit=1,
                )
                product = matches[0] if matches else None
            if not product:
                return ChatResponse(response="Which product would you like details about? Share its name or select it from the catalog.")
            return ChatResponse(response=self._ollama_answer(user_message, self._catalog_context([product])))

        if action == "add_to_cart":
            ids = client_context.get("recent_product_ids") or []
            product = self.search_tool.get_product_by_id(str(ids[0])) if ids else None
            if not product:
                return ChatResponse(
                    response="Tell me which product to add, or find it first in the catalog. I need a selected product before changing your cart."
                )
            if not product.get("in_stock"):
                return ChatResponse(response=f"{product['name']} is currently out of stock, so I can't add it to your cart.")
            logger.info("CART action=add product_id=%s", product["id"])
            return ChatResponse(
                response=f"[[SHOPAI_ADD_TO_CART:{product['id']}]]Added **{product['name']}** to your cart."
            )

        if action == "cart_action":
            cart = client_context.get("cart")
            if not isinstance(cart, list):
                cart = []
            if not cart:
                return ChatResponse(response="Your cart is empty. Find a product in the catalog and add it to your cart to see it here.")
            return ChatResponse(response=self._ollama_answer(user_message, {"cart": cart}))

        return ChatResponse(response=self._ollama_answer(user_message, {"business": "Poorvika electronics retailer"}))
