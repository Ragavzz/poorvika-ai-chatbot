"""Chat orchestration: Laya decision, catalog/cart operation, then Ollama response."""

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.laya_client import LayaClient
from app.services.llm_service import KNOWN_BRANDS, LLMService
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

    def _filters(self, message: str, intent: str = "product_search") -> Dict[str, Any]:
        # Laya selects the action. This small catalog vocabulary parser only extracts
        # filter values after that decision; it does not classify intent.
        parsed = LLMService._rule_based_intent_extraction(message)
        lowered = message.lower()
        # In an accessory description, the device after a compatibility link
        # is a search constraint, not the accessory's manufacturer/category.
        accessory_terms = (
            r"\b(?:accessor(?:y|ies)|case|cover|pouch|protector|tempered\s+glass|"
            r"screen\s+guard|cable|charger|adapter|holder|stand)\b"
        )
        compatibility = next((match for match in re.finditer(
            r"\b(?:for|compatible\s+with|fits)\s+(?=[a-z])", lowered
        ) if re.search(accessory_terms, lowered[:match.start()])), None)
        # A device family plus an alphanumeric model also identifies compatibility
        # in short names ("<device brand> <family> <model> <accessory>").
        device = None
        if re.search(accessory_terms, lowered):
            brands = "|".join(re.escape(brand.lower()) for brand in KNOWN_BRANDS)
            device = re.search(
                rf"(?<![a-z0-9])(?:{brands})\s+"
                r"(?:tabs?|tablets?|galaxy(?:\s+tab)?|ipad|iphone|pixel|surface|phones?|smartphones?)\s+"
                r"(?=[a-z0-9-]*[a-z])(?=[a-z0-9-]*\d)[a-z0-9-]+\b",
                lowered,
            )
        accessory = compatibility is not None or device is not None
        attribute_text = lowered[:compatibility.start()] if compatibility else lowered
        if device:
            attribute_text = attribute_text.replace(device.group(0), " ")
        if accessory:
            attributes = LLMService._rule_based_intent_extraction(attribute_text)
            parsed["brand"], parsed["category"] = attributes["brand"], attributes["category"]
        use_case = None
        if intent == "recommendation" and not accessory:
            match = re.search(
                r"\bfor\s+([a-z][a-z\s-]*?)(?=\s+(?:under|below|within|above|over|around|budget)\b|[?!.]|$)",
                lowered,
            )
            if match:
                use_case = match.group(1).strip()
                lowered = lowered[:match.start()] + lowered[match.end():]
        # Map category words as complete synonyms so "phone" cannot match
        # "Headphones" merely because the category contains that substring.
        if re.search(r"\baccessor(?:y|ies)\b", attribute_text):
            parsed["category"] = "accessories"
        elif re.search(r"\b(?:smartphones?|phones?|mobiles?|cell\s+phones?)\b", attribute_text):
            parsed["category"] = "Mobiles"
        elif re.search(r"\bearphones?\b", attribute_text):
            parsed["category"] = "Headphones"

        # In a details/cart instruction, "about" introduces a name, not a budget.
        around_terms = r"around|approximately|budget(?:\s+of)?" + ("" if accessory else r"|\bfor\b")
        if intent == "product_search":
            around_terms += "|about"
        around = re.search(rf"(?:{around_terms})\D{{0,8}}(\d[\d,]*(?:\.\d+)?)\s*(k)?\b", lowered)
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
        # Keep product/model terms (including model numbers), but remove
        # conversational, brand, category, and price-filter words generically.
        search_text = re.sub(
            r"\b(?:under|below|less\s+than|within|above|more\s+than|over|around|about|approximately)\s*(?:rs\.?|inr|rupees?|[^\w\s])?\s*\d[\d,]*(?:\.\d+)?\s*k?\b(?:\s*(?:rupees?|rs|inr)\b\.?)?",
            " ", lowered,
        )
        if accessory:
            # Full catalog spelling can survive token stemming and punctuation.
            # It is only an alternate text match; all attribute filters still apply.
            name = re.sub(
                r"^(?:please\s+)?(?:show(?:\s+me)?|find|search(?:\s+for)?|"
                r"tell\s+me\s+about|add|put|buy|increase\s+quantity\s+of)\s+",
                "", search_text,
            )
            name = re.sub(r"\s+(?:to|in)\s+(?:(?:my|the)\s+)?cart\s*$", "", name)
            parsed["exact_name"] = " ".join(name.split())
        ignored = {
            "show", "find", "search", "suggest", "recommend", "looking", "for",
            "a", "an", "the", "all", "good", "best", "me", "do", "does", "you", "have",
            "is", "are", "any", "which", "available", "need", "want", "can", "i",
            "get", "got", "please", "under", "below", "less", "than", "within",
            "around", "about", "approximately", "budget", "of", "over", "above",
            "more", "inr", "rs", "product", "products", "accessory", "accessories",
            "phone", "phones", "smartphone", "smartphones", "mobile", "mobiles", "cell",
            "earphone", "earphones",
        }
        if intent != "product_search":
            ignored.update({
                "tell", "give", "what", "detail", "details", "spec", "specs",
                "specification", "specifications", "feature", "features", "info",
                "information", "more", "its", "it", "this", "that", "them",
                "add", "put", "buy", "to", "my", "cart", "remove", "delete",
                "from", "increase", "decrease", "quantity", "the", "please",
                "by", "pick", "choose",
            })
        ignored.update(brand.lower() for brand in KNOWN_BRANDS
                       if not accessory or brand.lower() in attribute_text)
        if accessory:
            ignored.update({"compatible", "with", "fits"})
        qualifiers = []
        for token in re.findall(r"[a-z0-9]+", search_text):
            if token in ignored or token == "k":
                continue
            # Basic reusable English plural normalization, retaining model
            # numbers and unusual product names as written.
            if len(token) > 4 and token.endswith("ies"):
                token = token[:-3] + "y"
            elif len(token) > 3 and token.endswith("s"):
                token = token[:-1]
            qualifiers.append(token)
        parsed["search_term"] = " ".join(qualifiers) or None
        if intent == "recommendation":
            parsed["use_case"] = use_case
        return parsed

    def _find_products(self, filters: Dict[str, Any], *, limit: int = 5,
                       recommendation: bool = False, timings: Optional[Dict[str, Any]] = None) -> list:
        """One catalog retrieval path, retaining the existing search/filter implementation."""
        return self.search_tool.search_products(
            query=filters.get("search_term"), category=filters.get("category"),
            brand=filters.get("brand"), min_price=filters.get("min_price"),
            max_price=filters.get("max_price"), in_stock_only=recommendation,
            sort_by="rating" if recommendation else None, limit=limit, timings=timings,
            exact_name=filters.get("exact_name"),
        )

    def _resolve_product(self, message: str, context: Dict[str, Any], *, cart_only: bool = False) -> Optional[Dict[str, Any]]:
        """Resolve current names first; use recent selection only for unnamed references."""
        filters = self._filters(message, "product_details")
        reference = re.search(r"\b(?:it|this|that|them)\b", message, re.I)
        explicit = bool(filters.get("search_term") or filters.get("brand") or (filters.get("category") and not reference))
        cart_ids = {str(item.get("id")) for item in context.get("cart", []) if isinstance(item, dict)}
        if explicit:
            matches = self._find_products(filters, limit=100)
            requested = set((filters.get("search_term") or "").split())
            if requested:
                def specificity(product):
                    brand_words = set(re.findall(r"[a-z0-9]+", str(product.get("brand", "")).lower()))
                    name_words = set(re.findall(r"[a-z0-9]+", str(product.get("name", "")).lower()))
                    model = product.get("model") or str(product.get("name", "")).split("(")[0]
                    model_words = set(re.findall(r"[a-z0-9]+", str(model).lower())) - brand_words
                    requested_model = requested - brand_words
                    # A model explicitly named by the customer takes precedence
                    # over related models/accessories mentioning it in descriptions.
                    return (not requested.issubset(name_words), model_words != requested_model,
                            len(model_words - requested_model))
                matches.sort(key=specificity)
            if cart_only:
                return next((p for p in matches if str(p["id"]) in cart_ids), None)
            return matches[0] if matches else None
        for product_id in context.get("recent_product_ids") or []:
            if cart_only and str(product_id) not in cart_ids:
                continue
            product = self.search_tool.get_product_by_id(str(product_id))
            if product:
                return product
        return None

    def _cart_mutation_answer(self, message: str, context: Dict[str, Any], operation: str) -> str:
        product = self._resolve_product(message, context, cart_only=True)
        if not product:
            return "That product isn't in your cart. Please check the product name or select an item in your cart."
        item = next(p for p in context.get("cart", []) if str(p.get("id")) == str(product["id"]))
        quantity = int(item.get("quantity", 1))
        if operation == "increase" and not product.get("in_stock"):
            return f"{product['name']} is currently out of stock, so I can't increase its quantity."
        target = 0 if operation == "remove" else max(0, quantity + (1 if operation == "increase" else -1))
        command = dict(action=operation, product_id=str(product["id"]), expected_quantity=quantity, quantity=target)
        confirmation = (f"Removed **{product['name']}** from your cart." if target == 0
                        else f"Updated **{product['name']}** to {target} in your cart.")
        return f"[[SHOPAI_CART_ACTION:{json.dumps(command, separators=(',', ':'))}]]{confirmation}"

    def _catalog_context(self, products: list, **extra: Any) -> Dict[str, Any]:
        return {**self.ollama.product_context(products), **extra}

    @staticmethod
    def _format_catalog_search_answer(products: list, filters: Optional[Dict[str, Any]] = None) -> str:
        """Answer direct catalog lookups from the exact rows already returned by PostgreSQL in a clean Markdown table."""
        if not products:
            return "I couldn't find any products matching those filters. Try increasing your budget or searching for another model."

        rows = [
            "| Product | Brand | Price | Discount | Rating | Stock |",
            "|---|---|---:|---:|---:|---|",
        ]
        for p in products:
            name = p.get("name", "Product")
            brand = p.get("brand", "Unknown")
            price = f"₹{p.get('price', 0):,.0f}"
            discount_val = p.get("discount_percent", p.get("discount", 0.0)) or 0.0
            discount = f"{round(discount_val)}% OFF" if discount_val > 0 else "—"
            rating_val = p.get("rating")
            rating = f"{rating_val}★" if rating_val else "—"
            stock = "In Stock" if p.get("in_stock", p.get("inStock")) else "Out of Stock"
            rows.append(f"| {name} | {brand} | {price} | {discount} | {rating} | {stock} |")

        filters = filters or {}
        count = len(products)
        brands = {str(p.get("brand", "")).strip() for p in products}
        brand = next(iter(brands)) if filters.get("brand") and len(brands) == 1 else ""
        term = filters.get("search_term") or ""
        # Use the product's spelling only when the term describes every result.
        words = re.findall(r"[A-Za-z0-9]+", str(products[0].get("name", "")))
        canonical = {word.lower(): word for word in words}
        if term and all(term.lower() in str(p.get("name", "")).lower() for p in products):
            label = " ".join(canonical.get(word.lower(), word) for word in term.split())
        else:
            label = {"mobiles": "phone", "headphones": "earphone"}.get(
                str(filters.get("category") or "").lower(),
                str(filters.get("category") or "product").lower(),
            )
        if count != 1 and not label.endswith("s"):
            label += "s"
        label = f"{brand} {label}".strip()
        budget = ""
        if filters.get("min_price") is not None and filters.get("max_price") is not None:
            budget = f" between ₹{filters['min_price']:,.0f} and ₹{filters['max_price']:,.0f}"
        elif filters.get("max_price") is not None:
            budget = f" under ₹{filters['max_price']:,.0f}"
        elif filters.get("min_price") is not None:
            budget = f" above ₹{filters['min_price']:,.0f}"
        intro = f"I found {count} {label}{budget}:"
        all_in_stock = all(p.get("in_stock", p.get("inStock")) for p in products)
        stock_note = "These options are currently in stock. " if all_in_stock else "Availability is shown above. "
        outro = stock_note + "Let me know if you'd like details about any of them."
        return f"{intro}\n\n" + "\n".join(rows) + f"\n\n{outro}"

    @staticmethod
    def _format_product_details_answer(product: Dict[str, Any]) -> str:
        """Formats structured, comprehensive product details from PostgreSQL catalog without adding to cart."""
        name = product.get("name", "Product")
        brand = product.get("brand", "Unknown")
        price = product.get("price", 0)
        mrp = product.get("mrp")
        discount = product.get("discount_percent", 0.0) or 0.0
        stock_status = "In Stock" if product.get("in_stock") else "Out of Stock"
        rating = product.get("rating")
        rating_count = product.get("rating_count", 0)
        rating_str = f"{rating}★ ({rating_count} review{'s' if rating_count != 1 else ''})" if rating else "Not rated yet"
        category = product.get("category", "General")

        lines = [
            f"### **{name}**",
            f"- **Brand:** {brand}",
            f"- **Category:** {category}",
            f"- **Price:** ₹{price:,.0f}" + (f" *(MRP: ₹{mrp:,.0f}, {round(discount)}% OFF)*" if mrp and mrp > price else ""),
            f"- **Availability:** {stock_status}",
            f"- **Rating:** {rating_str}",
        ]

        specs = product.get("flattened_specs") or {}
        if specs:
            lines.append("\n**Key Specifications:**")
            spec_count = 0
            for k, v in specs.items():
                if k not in ("Generic Name",):
                    lines.append(f"- **{k}:** {v}")
                    spec_count += 1
                    if spec_count >= 8:
                        break

        description = (product.get("description") or "").strip()
        if description and description != name:
            clean_desc = description[:250].strip() + ("..." if len(description) > 250 else "")
            lines.append(f"\n{clean_desc}")

        return "\n".join(lines)

    @staticmethod
    def _format_cart_answer(cart: list, query: str = "") -> str:
        """Answers cart inquiries grounded exclusively in the frontend's actual current cart state."""
        if not cart:
            return "Your cart is currently empty. Find a product in the catalog and add it to your cart to see it here."

        total_items = sum(int(item.get("quantity", 1)) for item in cart)
        subtotal = sum(float(item.get("price", 0)) * int(item.get("quantity", 1)) for item in cart)

        query_l = query.lower()
        is_total_query = any(k in query_l for k in ["total", "how much", "amount", "cost", "value"]) and not any(k in query_l for k in ["show", "items", "what is in", "list"])

        if is_total_query:
            return f"Your current cart total is **₹{subtotal:,.0f}** for {total_items} item{'s' if total_items != 1 else ''}."

        lines = [f"Here are the items in your cart:\n"]
        for item in cart:
            product_id = item.get("id")
            name = item.get("name", "Product")
            qty = int(item.get("quantity", 1))
            unit_price = float(item.get("price", 0))
            item_total = unit_price * qty
            id_label = f" (ID: {product_id})" if product_id is not None else ""
            lines.append(f"- **{name}**{id_label} (Qty: {qty}) — ₹{unit_price:,.0f} each (₹{item_total:,.0f})")

        lines.append(f"\n**Total: ₹{subtotal:,.0f}** ({total_items} items)")
        return "\n".join(lines)

    @staticmethod
    def _format_general_conversation(query: str) -> Optional[str]:
        """Provides natural conversational replies without product mutations."""
        q = query.lower().strip()
        if re.search(r"^(?:thank\s*you|thanks|many\s*thanks)[\s.!]*$", q):
            return "You're welcome! Let me know if you need anything else."
        if re.search(r"^(?:okay|ok|great|nice|cool|got\s*it|perfect|that\'?s\s*helpful|understood)[\s.!]*$", q):
            return "Glad to hear! How else can I assist you with your shopping today?"
        if re.search(r"^(?:hi|hello|hey|namaste|good\s*(?:morning|afternoon|evening))[\s.!]*$", q):
            return "Tell me what you're looking for, and I'll help you choose."
        if re.search(r"^(?:bye|goodbye|see\s*you)[\s.!]*$", q):
            return "Thank you for visiting Poorvika! Have a great day!"
        return None

    def _ollama_answer(self, message: str, context: Dict[str, Any], timings: Dict[str, Any]) -> str:
        try:
            logger.info("[AI FLOW] OLLAMA CALL: model=%s, url=%s", self.ollama.model, self.ollama.url)
            answer = self.ollama.generate(message, context, timings=timings)
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

    async def generate_response(self, request: ChatRequest, timings: Dict[str, Any] | None = None) -> ChatResponse:
        timings = timings if timings is not None else {}
        full_message = (request.message or "").strip()
        user_message, client_context = self._request_context(full_message)
        if not user_message:
            return ChatResponse(response="Please provide a message or question about what you're shopping for.")

        # Laya must be the first decision step. Never fall back to a regex intent guess.
        laya_started = time.perf_counter()
        timings["laya_start"] = datetime.now(timezone.utc).isoformat()
        timings["laya_call_count"] = timings.get("laya_call_count", 0) + 1
        try:
            decision = await run_in_threadpool(self.laya.decide, user_message)
        except Exception:
            timings["laya_end"] = datetime.now(timezone.utc).isoformat()
            timings["laya_duration_ms"] = round((time.perf_counter() - laya_started) * 1000, 1)
            logger.info("CHAT TIMING laya_ms=%.1f", (time.perf_counter() - laya_started) * 1000)
            logger.exception("LAYA decision failed")
            return ChatResponse(
                response="The configured Laya decision service is unavailable or returned an invalid decision. Please try again shortly."
            )
        timings["laya_end"] = datetime.now(timezone.utc).isoformat()
        timings["laya_duration_ms"] = round((time.perf_counter() - laya_started) * 1000, 1)
        logger.info("CHAT TIMING laya_ms=%.1f", timings["laya_duration_ms"])

        laya_choice = decision["choice"]
        action = laya_choice
        confidence = decision.get("confidence")
        logger.info(
            "[AI FLOW] LAYA DECISION: choice=%s, confidence=%s, source=%s",
            action, confidence, decision.get("source"),
        )
        logger.info("DECISION action=%s confidence=%s", action, confidence)

        # Deterministic Safety Boundary & Intent Disambiguation
        conversational_re = re.search(
            r"^(?:thank\s*you|thanks|many\s*thanks|okay|ok|great|nice|cool|got\s*it|perfect|that\'?s\s*helpful|understood|bye|goodbye|hello|hi|hey)[\s.!]*$",
            user_message, re.I
        )
        details_re = re.search(
            r"\b(?:tell\s*(?:me\s*)?about(?:\s+it|\s+this)?|what\s+are\s+its\s+(?:specs|features|specifications)|give\s+details|product\s+details|specs|specifications|features|more\s+details|more\s+info|about\s+it)\b",
            user_message, re.I
        )
        cart_view_re = re.search(
            r"\b(?:show\s+(?:items\s+in\s+)?cart|what(?:\s+is|'s|’s)\s+in\s+(?:my\s+)?cart|show\s+my\s+cart|^cart$|how\s+much\s+is\s+(?:my\s+)?cart|what\s+is\s+(?:my\s+)?cart\s+total|cart\s+total|view\s+cart)\b",
            user_message, re.I
        )
        add_to_cart_re = re.search(
            r"^(?:(?:can|could|would)\s+you\s+|i(?:'d|\s+would)?\s+like\s+to\s+|i\s+want\s+to\s+)?(?:please\s+)?(?:add\s+(?:.+?\s+)?to\s+(?:my\s+)?cart|buy\s+(?:it|this)|put\s+.+?\s+in\s+(?:my\s+)?cart|add\s+this\s+phone|add\s+this|add\s+it)\b",
            user_message, re.I
        )
        cart_operation_re = re.search(
            r"^(?:please\s+)?(?:(remove|delete)\s+.+?\s+from\s+(?:my\s+)?cart|(increase|decrease)\s+(?:the\s+)?quantity\b)",
            user_message, re.I,
        )
        cart_operation = None
        if cart_operation_re:
            cart_operation = "remove" if cart_operation_re.group(1) else cart_operation_re.group(2).lower()

        if conversational_re:
            action = "general_query"
        elif cart_operation:
            action = "cart_action"
        elif details_re and not add_to_cart_re:
            action = "product_details"
        elif cart_view_re and not add_to_cart_re:
            action = "cart_action"
        elif add_to_cart_re:
            action = "add_to_cart"
        elif action == "add_to_cart" and not add_to_cart_re:
            # Disambiguate when Laya returns add_to_cart for non-purchase queries
            if details_re:
                action = "product_details"
            elif cart_view_re:
                action = "cart_action"
            else:
                action = "general_query"

        # Only product-page suggestion clicks carry this existing-context extension.
        # Laya has already run above; preserve ordinary manual search/cart behavior.
        suggestion_product = None
        suggestion_id = client_context.get("suggestion_product_id")
        if isinstance(suggestion_id, str) and suggestion_id in (client_context.get("recent_product_ids") or []):
            suggestion_product = self.search_tool.get_product_by_id(suggestion_id)
        suggestion_discovery = re.search(
            r"^(?:please\s+)?(?:show|find|search|suggest|recommend|compare|list)\b|\b(?:alternatives?|similar\s+products?|other\s+phones?)\b",
            user_message, re.I,
        )
        suggestion_information = bool(
            suggestion_product and not suggestion_discovery and not add_to_cart_re
            and not cart_operation and not cart_view_re and not conversational_re
            and re.search(r"^(?:is|are|does|do|can|could|will|would|how|what|which)\b", user_message, re.I)
        )
        if suggestion_information:
            action = "general_query"
            logger.info("[AI FLOW] SUGGESTION CONTEXT: informational question uses general_query after Laya %s", laya_choice)

        discovery_request = re.search(
            r"\b(?:show|find|search|need|want|looking for|do you have|have you got|can i get|available|any)\b",
            user_message, re.I,
        )
        if discovery_request and not suggestion_information and not cart_operation and not cart_view_re and not add_to_cart_re and not details_re and action in (
            "general_query", "cart_action", "product_details"
        ):
            action = "product_search"
            logger.info("[AI FLOW] ACTION RECOVERY: natural product discovery overrides Laya %s", laya_choice)

        # Laya may classify a bare catalog phrase (for example, "Apple iPhone 15")
        # as a general query or purchase action. Search terms and SQL existence
        # checks below are the deterministic catalog route; only an explicit
        # purchase command may mutate the cart.
        if (
            action in ("general_query", "add_to_cart")
            and not suggestion_information and not conversational_re and not cart_operation and not details_re and not cart_view_re and not add_to_cart_re
        ):
            candidate_filters = self._filters(user_message)
            has_catalog_terms = bool(
                candidate_filters.get("search_term")
                or candidate_filters.get("brand")
                or candidate_filters.get("category")
            )
            if has_catalog_terms:
                action = "product_search"
                logger.info("[AI FLOW] ACTION RECOVERY: catalog phrase overrides Laya %s", laya_choice)

        logger.info("[AI FLOW] INTENT/ACTION: %s (Laya choice: %s)", action, laya_choice)
        logger.info("TOOL/DATABASE action=%s", action)

        if action in ("product_search", "recommendation"):
            extraction_started = time.perf_counter()
            filters = self._filters(user_message, action)
            if suggestion_product and re.search(r"\bsimilar\s+products?\b", user_message, re.I):
                filters["search_term"] = None
                filters["category"] = suggestion_product.get("category")
            logger.info("CHAT TIMING product_filter_extraction_ms=%.1f filters=%s", (time.perf_counter() - extraction_started) * 1000, filters)
            logger.info("[AI FLOW] EXTRACTED FILTERS: %s", filters)
            db_started = time.perf_counter()
            timings["product_search_start"] = datetime.now(timezone.utc).isoformat()
            products = self._find_products(filters, recommendation=action == "recommendation", timings=timings)
            timings["product_search_end"] = datetime.now(timezone.utc).isoformat()
            timings["product_search_duration_ms"] = round((time.perf_counter() - db_started) * 1000, 1)
            logger.info("CHAT TIMING product_search_ms=%.1f postgres_query_ms=%.1f", timings["product_search_duration_ms"], timings.get("postgres_query_duration_ms", 0.0))
            logger.info("TOOL/DATABASE returned %d products", len(products))
            logger.info("[AI FLOW] PRODUCT TOOL: %d products found", len(products))
            if action == "product_search":
                # The query has already been applied in PostgreSQL, and a
                # direct lookup needs only exact catalog facts. Return formatted Markdown table.
                response = self._format_catalog_search_answer(products, filters)
                self._response_source = "deterministic_catalog"
                timings["ollama_skipped_reason"] = "deterministic_catalog_search"
                logger.info("[AI FLOW] OLLAMA SKIPPED: exact product-search facts are available from PostgreSQL")
            else:
                # Rating/availability are verified catalog signals, not a performance benchmark.
                response = self._format_catalog_search_answer(products, filters)
                if products:
                    response = "Here are in-stock options ranked by customer rating:\n\n" + response
                    if filters.get("use_case"):
                        response += f"\n\nI don't have verified performance comparisons for {filters['use_case']}, so these are suggestions based on availability, price and customer ratings."
                self._response_source = "deterministic_recommendation"
                timings["ollama_skipped_reason"] = "grounded_recommendation_candidates"
            if products:
                ids = [str(product["id"]) for product in products]
                response += f"\n\n[[SHOPAI_PRODUCTS:{','.join(ids)}]]"
            logger.info("[AI FLOW] FINAL RESPONSE: source=%s", self._response_source)
            return ChatResponse(response=response)

        if action == "product_details":
            product = self._resolve_product(user_message, client_context)
            if not product:
                return ChatResponse(response="Which product would you like details about? Share its name or select it from the catalog.")
            # Format structured, authoritative product details from PostgreSQL catalog without mutating cart
            response = self._format_product_details_answer(product)
            self._response_source = "deterministic_catalog"
            return ChatResponse(response=response + f"\n\n[[SHOPAI_PRODUCTS:{product['id']}]]")

        if action == "add_to_cart":
            product = self._resolve_product(user_message, client_context)
            if not product:
                return ChatResponse(
                    response="Tell me which product to add, or find it first in the catalog. I need a selected product before changing your cart."
                )
            if not product.get("in_stock"):
                return ChatResponse(response=f"{product['name']} is currently out of stock, so I can't add it to your cart.")
            logger.info("CART action=add product_id=%s", product["id"])
            return ChatResponse(
                response=f"[[SHOPAI_PRODUCTS:{product['id']}]][[SHOPAI_ADD_TO_CART:{product['id']}]]Added **{product['name']}** to your cart.\n₹{product['price']:,.0f} • In Stock"
            )

        if action == "cart_action":
            cart = client_context.get("cart")
            if not isinstance(cart, list):
                cart = []
            client_context["cart"] = cart
            response = (self._cart_mutation_answer(user_message, client_context, cart_operation)
                        if cart_operation else self._format_cart_answer(cart, user_message))
            self._response_source = "cart_state"
            return ChatResponse(response=response)

        # General conversational acknowledgment (thank you, thanks, okay, greetings)
        conversational_reply = self._format_general_conversation(user_message)
        if conversational_reply:
            self._response_source = "conversational"
            return ChatResponse(response=conversational_reply)

        context = {"business": "Poorvika electronics retailer"}
        if suggestion_information:
            context["suggestion_information"] = True
            context["products"] = [{
                key: suggestion_product.get(key)
                for key in ("id", "name", "brand", "category", "price", "in_stock", "flattened_specs", "description")
            }]
        return ChatResponse(response=await run_in_threadpool(self._ollama_answer, user_message, context, timings))
