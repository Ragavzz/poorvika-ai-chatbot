"""LLM Service orchestrating Ollama Cloud interactions.

Implements:
1. Natural language intent and structured filter extraction via Ollama Cloud.
2. Grounded conversational response generation strictly based on real PostgreSQL rows.
"""

import os
import re
import json
import logging
import time
from typing import Dict, Any, List, Optional
import requests
from app.config import settings

logger = logging.getLogger("shopai.services.llm")

# Known categories and brands from Poorvika dataset for reference in prompts
KNOWN_CATEGORIES = [
    "Data Cables", "Irons", "Voltage Stabilizers", "Battery Chargers",
    "Cases & Covers", "Headphones", "Mixers Grinders & Juicers",
    "Air Coolers", "Fans", "Air Fryers", "Power Banks", "Pendrives",
    "Memory Cards", "Surge Protector", "Smartwatches", "AirTag", "Smartphones", "Laptops"
]

KNOWN_BRANDS = [
    "Apple", "Philips", "V-Guard", "Samsung", "Mi", "Crompton",
    "Premier", "Bosch", "Inbase", "Symphony", "Conekt", "SanDisk",
    "Zebronics", "Bajaj", "Sony", "Gripp", "FABER", "Orient", "Butterfly", "PowerUp"
]


class LLMService:
    """Ollama Cloud client for intent parsing and grounded response generation."""

    def __init__(self):
        self.api_key = settings.OLLAMA_API_KEY or os.environ.get("OLLAMA_API_KEY", "").strip()
        self.api_url = settings.OLLAMA_API_URL
        self.model = settings.OLLAMA_MODEL
        self.timeout = 20

    def _call_ollama(self, messages: List[Dict[str, str]], temperature: float = 0.1) -> Optional[str]:
        """Dispatches chat request to Ollama Cloud API."""
        if not self.api_key:
            logger.warning("OLLAMA_API_KEY is not set. Using local fallback parsing/formatting.")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }

        try:
            started = time.perf_counter()
            resp = requests.post(self.api_url, headers=headers, json=payload, timeout=self.timeout)
            logger.info("CHAT TIMING ollama_call_ms=%.1f status=%s purpose=legacy_llm_service", (time.perf_counter() - started) * 1000, resp.status_code)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("message", {}).get("content", "").strip()
            else:
                logger.warning(f"Ollama Cloud returned status {resp.status_code}: {resp.text[:150]}")
                return None
        except Exception as e:
            if "started" in locals():
                logger.info("CHAT TIMING ollama_call_ms=%.1f purpose=legacy_llm_service error=%s", (time.perf_counter() - started) * 1000, type(e).__name__)
            logger.warning(f"Ollama Cloud request failed: {e}")
            return None

    def extract_intent_and_filters(self, query: str) -> Dict[str, Any]:
        """
        Extracts structured search parameters from user query via Ollama Cloud.
        Falls back to rule-based parsing if LLM is unavailable.
        """
        system_prompt = (
            "You are an e-commerce query analyzer. Analyze the customer's input and extract search filters.\n"
            "Respond ONLY with a valid JSON object with these keys:\n"
            "- intent: 'product_search' | 'greeting' | 'policy' | 'general'\n"
            "- category: string category if mentioned (e.g., 'Headphones', 'Data Cables', 'Irons', 'Power Banks', 'Air Coolers'), or null\n"
            "- brand: string brand if mentioned (e.g., 'Sony', 'Apple', 'Philips', 'Samsung', 'Mi'), or null\n"
            "- max_price: numeric maximum budget float/int, or null\n"
            "- min_price: numeric minimum budget float/int, or null\n"
            "- search_term: concise keyword for database search, or null\n"
            "Do not include explanation. Output strictly valid JSON."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]

        raw_llm = self._call_ollama(messages, temperature=0.0)
        if raw_llm:
            parsed = self._extract_json(raw_llm)
            if parsed and isinstance(parsed, dict) and "intent" in parsed:
                return parsed

        # Rule-based fallback if Ollama call fails or returns non-JSON
        return self._rule_based_intent_extraction(query)

    def generate_grounded_response(self, user_query: str, products: List[Dict[str, Any]]) -> str:
        """
        Synthesizes an intelligent, conversational response strictly grounded in PostgreSQL rows.
        The chatbot NEVER invents products, prices, or specs not present in products list.
        """
        if not products:
            return (
                "I searched our catalog in the database, but couldn't find any products matching those exact criteria.\n\n"
                "Try adjusting your budget or searching for categories like **Headphones**, **Data Cables**, **Irons**, **Power Banks**, or brands like **Sony**, **Apple**, **Samsung**, **Philips**."
            )

        # Build context from real database rows
        product_summaries = []
        for i, p in enumerate(products[:5], 1):
            specs = p.get("flattened_specs", {}) or {}
            key_specs = []
            for k in ["Model Name", "Headphone Type", "Power Consumption", "Capacity", "Warranty Summary"]:
                if k in specs:
                    key_specs.append(f"{k}: {specs[k]}")

            spec_text = " | ".join(key_specs) if key_specs else "Standard specifications"
            avail = "In Stock" if p.get("in_stock") else "Out of Stock"
            stock_cnt = p.get("stock", 0)
            rating_text = f"{p.get('rating')} / 5 ({p.get('rating_count', 0)} reviews)" if p.get("rating") else "Not yet rated"

            product_summaries.append(
                f"{i}. {p.get('name')} | Brand: {p.get('brand')} | Category: {p.get('category')} | "
                f"Price: ₹{int(p.get('price', 0)):,} (MRP: ₹{int(p.get('mrp', 0) or p.get('price', 0)):,}, {int(p.get('discount_percent', 0))}% OFF) | "
                f"Status: {avail} ({stock_cnt} units) | Rating: {rating_text} | Specs: {spec_text}"
            )

        context_block = "\n".join(product_summaries)

        system_prompt = (
            "You are ShopAI, a helpful, polite e-commerce shopping assistant.\n"
            "CRITICAL RULES:\n"
            "1. Ground your response strictly in the REAL products provided below from our PostgreSQL database.\n"
            "2. Never invent, hallucinate, or assume product names, prices, discounts, stock, or specifications.\n"
            "3. Format your response cleanly using GitHub-flavored Markdown:\n"
            "   - Use bold for product names, brands, and prices (e.g. **₹829**).\n"
            "   - Clearly mention current price, discount, in-stock status, and top features.\n"
            "   - Keep it engaging, concise, and easy to read on mobile.\n"
            "   - End by asking if they would like more details or assistance choosing."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Customer asked: \"{user_query}\"\n\n"
                    f"Real matching products from PostgreSQL database:\n{context_block}\n\n"
                    f"Provide your grounded recommendation response."
                ),
            },
        ]

        llm_reply = self._call_ollama(messages, temperature=0.3)
        if llm_reply and len(llm_reply.strip()) > 20:
            return llm_reply.strip()

        # Deterministic markdown formatter fallback
        return self._format_products_markdown(user_query, products)

    @staticmethod
    def _extract_json(raw_text: str) -> Optional[Dict[str, Any]]:
        """Safely parses JSON substring from model output."""
        text = raw_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        return None

    @staticmethod
    def _rule_based_intent_extraction(query: str) -> Dict[str, Any]:
        """Deterministic parser used if Ollama Cloud is offline or rate-limited."""
        q = query.lower().strip()

        # Check greeting
        if q in ["hi", "hello", "hey", "good morning", "good evening", "namaste"]:
            return {"intent": "greeting", "category": None, "brand": None, "max_price": None, "min_price": None, "search_term": None}

        # Check brand
        detected_brand = None
        for b in KNOWN_BRANDS:
            if b.lower() in q:
                detected_brand = b
                break

        # Check category
        detected_category = None
        for c in KNOWN_CATEGORIES:
            if c.lower() in q or c.lower()[:-1] in q:
                detected_category = c
                break

        # Check prices
        max_price = None
        min_price = None
        price_patterns = [
            r"(?:under|below|less than|within)\s*(?:rs\.?|inr|₹)?\s*(\d+[\d,]*)(k)?",
            r"(?:above|more than|over)\s*(?:rs\.?|inr|₹)?\s*(\d+[\d,]*)(k)?",
        ]
        m_max = re.search(price_patterns[0], q)
        if m_max:
            val = float(m_max.group(1).replace(",", ""))
            if m_max.group(2) and m_max.group(2).lower() == "k":
                val *= 1000.0
            max_price = val

        m_min = re.search(price_patterns[1], q)
        if m_min:
            val = float(m_min.group(1).replace(",", ""))
            if m_min.group(2) and m_min.group(2).lower() == "k":
                val *= 1000.0
            min_price = val

        return {
            "intent": "product_search",
            "category": detected_category,
            "brand": detected_brand,
            "max_price": max_price,
            "min_price": min_price,
            "search_term": q if not (detected_brand or detected_category) else None,
        }

    @staticmethod
    def _format_products_markdown(query: str, products: List[Dict[str, Any]]) -> str:
        """Formats products into markdown directly."""
        lines = [f"Here are the top options from our catalog matching your request:\n"]
        for p in products[:4]:
            name = p.get("name", "Product")
            price = int(p.get("price", 0))
            mrp = int(p.get("mrp", 0) or price)
            discount = int(p.get("discount_percent", 0))
            brand = p.get("brand", "")
            avail = "In Stock" if p.get("in_stock") else "Out of Stock"
            stock = p.get("stock", 0)

            price_str = f"**₹{price:,}**"
            if mrp > price and discount > 0:
                price_str += f" ~~₹{mrp:,}~~ (*{discount}% OFF*)"

            lines.append(f"### {name}")
            lines.append(f"- **Price:** {price_str}")
            lines.append(f"- **Brand:** {brand} | **Availability:** {avail} ({stock} units)")

            specs = p.get("flattened_specs", {})
            if specs:
                sample_specs = [f"**{k}:** {v}" for k, v in list(specs.items())[:3] if v]
                if sample_specs:
                    lines.append(f"- **Details:** {' | '.join(sample_specs)}")
            lines.append("")

        lines.append("Would you like more details or assistance placing an order?")
        return "\n".join(lines)
