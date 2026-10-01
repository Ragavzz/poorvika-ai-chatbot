"""Local Ollama chat generation for grounded Poorvika responses."""

import json
import logging
import time
from typing import Any, Dict, List

import requests

from app.config import settings

logger = logging.getLogger("shopai.services.ollama")
HTTP = requests.Session()

SYSTEM_PROMPT = (
    "Use only catalog data. Answer in one concise sentence with product name, exact INR price, "
    "and stock status. Use ₹ before the exact catalog price; never change its currency or value. "
    "Do not invent or infer product details."
)


class OllamaService:
    """Generate a final natural-language answer with the configured local model."""

    def __init__(self) -> None:
        self.url = settings.OLLAMA_API_URL
        self.model = settings.OLLAMA_MODEL

    def generate(self, message: str, context: Dict[str, Any]) -> str:
        logger.info("OLLAMA request: model=%s", self.model)
        started = time.perf_counter()
        # Serialize only the already-filtered rows returned by PostgreSQL. This
        # is compact and avoids Python's verbose dict representation in prompts.
        products = context.get("products")
        if products:
            fields = ("name", "price", "in_stock")
            catalog = [
                {**{key: product.get(key) for key in fields}, "currency": "INR"}
                for product in products
            ]
            prompt = f"Customer: {message}\nCatalog: {json.dumps(catalog, ensure_ascii=False, separators=(',', ':'))}"
        else:
            prompt = f"Customer: {message}\nContext: {json.dumps(context, ensure_ascii=False, separators=(',', ':'))}"
        logger.info("OLLAMA prompt_chars=%d", len(SYSTEM_PROMPT) + len(prompt))
        try:
            response = HTTP.post(
                self.url,
                json={
                    "model": self.model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "keep_alive": "10m",
                    "options": {"temperature": 0.1, "num_predict": 72, "num_ctx": 2048},
                },
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.info("CHAT TIMING ollama_call_ms=%.1f status=%s error=%s", (time.perf_counter() - started) * 1000, status, type(exc).__name__)
            raise
        content = (data.get("message") or {}).get("content", "").strip()
        if not content:
            logger.info("CHAT TIMING ollama_call_ms=%.1f status=%s empty=true", (time.perf_counter() - started) * 1000, response.status_code)
            raise ValueError("Ollama returned an empty response")
        logger.info("OLLAMA response received (%d characters)", len(content))
        logger.info(
            "CHAT TIMING ollama_call_ms=%.1f status=%s load_ms=%.1f prompt_eval_ms=%.1f eval_ms=%.1f eval_tokens=%s",
            (time.perf_counter() - started) * 1000,
            response.status_code,
            (data.get("load_duration") or 0) / 1_000_000,
            (data.get("prompt_eval_duration") or 0) / 1_000_000,
            (data.get("eval_duration") or 0) / 1_000_000,
            data.get("eval_count"),
        )
        return content

    @staticmethod
    def product_context(products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Keep only catalog-backed fields in the prompt context."""
        return {
            "products": [
                {
                    key: product.get(key)
                    for key in (
                        "id", "name", "brand", "model", "category", "price", "mrp",
                        "discount_percent", "in_stock", "stock", "rating", "rating_count",
                        # Names, price, stock and rating are enough for concise
                        # product recommendations; large raw descriptions/specs
                        # needlessly inflate local inference prompts.
                    )
                }
                for product in products
            ]
        }
