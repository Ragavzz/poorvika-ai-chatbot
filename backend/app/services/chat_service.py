"""Chat orchestration: configured decision, catalog/cart operation, optional generation."""

import json
import asyncio
from collections import OrderedDict
import logging
import re
import time
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.decision_provider import create_decision_provider, is_greeting
from app.config import settings
from app.services.cart_queries import is_cart_total_query, format_inr
from app.services.cart_operations import parse_cart_operation
from app.services.llm_service import KNOWN_BRANDS, LLMService
from app.services.ollama_service import OllamaService
from app.tools.product_search_tool import ProductSearchTool
from app.models.product import Product

logger = logging.getLogger("shopai.services.chat")
CLIENT_CONTEXT_RE = re.compile(r"\n\n<shopai_client_context>(.*?)</shopai_client_context>\s*$", re.S)
LOW_CONFIDENCE = 0.15
# Process-local, expiring conversation store; no shared default conversation.
SESSIONS = OrderedDict()
SESSION_TTL = 3600
SESSION_LIMIT = 512


class ChatService:
    """Route each request through its configured provider and existing business logic."""

    def __init__(self, db: Session):
        self.db = db
        self.laya = create_decision_provider()
        self.ollama = OllamaService()
        self.search_tool = ProductSearchTool(db=db)
        self._response_source = "deterministic_clarification"

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
        # The configured provider selects the action. This catalog parser extracts
        # filter values after that decision; it does not classify intent.
        parsed = LLMService._rule_based_intent_extraction(message)
        lowered = message.lower()
        catalog_brands = [row[0] for row in self.db.query(Product.brand).distinct() if row[0]]
        for brand in sorted(catalog_brands if intent in ("product_search", "recommendation") else [], key=len, reverse=True):
            if re.search(r"(?<!\w)" + re.escape(brand.lower()) + r"(?!\w)", lowered):
                parsed["brand"] = brand
                break
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
        elif re.search(r"\blaptops?\b", attribute_text):
            parsed["category"] = "laptops"
        elif re.search(r"\bearphones?\b", attribute_text):
            parsed["category"] = "Headphones"
        if not accessory:
            categories = [category for pattern, category in (
                (r"\b(?:smartphones?|phones?|mobiles?)\b", "Mobiles"),
                (r"\blaptops?\b", "laptops"),
                (r"\b(?:earphones?|headphones?)\b", "Headphones"),
                (r"\b(?:televisions?|tvs?)\b", "television"),
            ) if re.search(pattern, attribute_text)]
            if len(categories) > 1:
                parsed["category"] = categories

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
            "earphone", "earphones", "laptop", "laptops", "only", "similar",
            "another", "option", "options", "ones", "and", "headphone", "headphones",
            "television", "televisions", "tv", "tvs",
        }
        if intent != "product_search":
            ignored.update({
                "tell", "give", "what", "detail", "details", "spec", "specs",
                "specification", "specifications", "feature", "features", "info",
                "information", "more", "its", "it", "this", "that", "them",
                "add", "put", "buy", "to", "my", "cart", "remove", "delete",
                "from", "increase", "decrease", "quantity", "the", "please",
                "by", "pick", "choose", "price", "stock", "available", "has",
                "first", "second", "third", "fourth", "fifth", "cheapest", "cheaper",
            })
            if re.search(r"\b(?:which|this|that)\s+one\b", lowered):
                ignored.add("one")
        ignored.update(brand.lower() for brand in [*KNOWN_BRANDS, *(catalog_brands if intent in ("product_search", "recommendation") else [])]
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
        if isinstance(filters.get("category"), list):
            groups = [self._find_products({**filters, "category": category}, limit=limit,
                                         recommendation=recommendation, timings=timings)
                      for category in filters["category"]]
            filters["unmatched_categories"] = [category for category, rows in zip(filters["category"], groups) if not rows]
            products, seen = [], set()
            for index in range(limit):
                for rows in groups:
                    if index < len(rows) and str(rows[index]["id"]) not in seen:
                        seen.add(str(rows[index]["id"]))
                        products.append(rows[index])
                        if len(products) == limit:
                            return products
            return products
        return self.search_tool.search_products(
            query=filters.get("search_term"), category=filters.get("category"),
            brand=filters.get("brand"), min_price=filters.get("min_price"),
            max_price=filters.get("max_price"), in_stock_only=recommendation or filters.get("in_stock_only", False),
            sort_by="rating" if recommendation else None, limit=limit, timings=timings,
            exact_name=filters.get("exact_name"), exclude_ids=filters.get("exclude_ids"),
        )

    def _resolve_product(self, message: str, context: Dict[str, Any], *, cart_only: bool = False) -> Optional[Dict[str, Any]]:
        """Resolve current names first; use recent selection only for unnamed references."""
        filters = self._filters(message, "product_details")
        reference = re.search(r"\b(?:it|this|that|them)\b", message, re.I)
        if re.search(r"\b(?:first|second|third|fourth|fifth|cheapest|cheaper|its)\b|^(?:which one|what is its|is it)\b", message, re.I):
            filters["search_term"] = None
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
        products = [self.search_tool.get_product_by_id(str(pid))
                    for pid in context.get("recent_product_ids") or []]
        products = [p for p in products if p and (not cart_only or str(p["id"]) in cart_ids)]
        ordinal = re.search(r"\b(first|second|third|fourth|fifth)\b", message, re.I)
        if ordinal:
            index = ["first", "second", "third", "fourth", "fifth"].index(ordinal.group(1).lower())
            return products[index] if index < len(products) else None
        if re.search(r"\b(?:cheapest|cheaper)\b", message, re.I) and products:
            lowest = min(p["price"] for p in products)
            products = [p for p in products if p["price"] == lowest]
        selected = context.get("selected_product_id")
        if len(products) > 1 and selected and not re.search(r"cheapest|cheaper", message, re.I):
            products = [p for p in products if str(p["id"]) == selected]
        product = products[0] if len(products) == 1 else None
        if product:
            context["selected_product_id"] = str(product["id"])
        return product

    def _cart_mutation_answer(self, message: str, context: Dict[str, Any], operation: str) -> str:
        # Resolve against the actual client cart, never against catalog search terms.
        cart = []
        for item in context.get("cart", []):
            if not isinstance(item, dict):
                continue
            catalog = self.search_tool.get_product_by_id(str(item.get("id")))
            cart.append({**item, "name": catalog["name"] if catalog else item.get("name", "")})
        parsed = parse_cart_operation(message)
        phrase = parsed["reference"].lower() if parsed else ""
        explicit_name = bool(phrase and not re.fullmatch(r"(?:(?:the|that|this)\s+)?(?:product|item|one|it)|(?:the\s+)?(?:first|second|third|fourth|fifth)(?:\s+(?:product|item))?", phrase))
        candidates = cart
        named = []
        if explicit_name:
            # IDs are authoritative. If the user supplied an ID, don't let a
            # similar product name select a different line.
            id_matches = [item for item in cart if item.get("id") and re.search(
                r"(?<![\w-])" + re.escape(str(item["id"])) + r"(?![\w-])", message, re.I)]
            if id_matches:
                named = id_matches
            else:
                requested = self._cart_name_tokens(phrase)
                for item in cart:
                    name = str(item.get("name") or "")
                    item_tokens = self._cart_name_tokens(name)
                    # Match only against this cart line's canonical display
                    # name. Singular/plural normalization handles requests
                    # such as “earphones” for catalog “Earphone”.
                    if requested and requested.issubset(item_tokens):
                        named.append(item)
                if not named:
                    cart_summary = self._format_cart_answer(cart, "show cart")
                    return ("That product isn't in your cart. Your current cart is:\n\n" + cart_summary)
        ordinal = re.search(r"\b(first|second|third|fourth|fifth)\b", message, re.I)
        if named:
            candidates = named
        elif ordinal:
            index = ["first", "second", "third", "fourth", "fifth"].index(ordinal.group(1).lower())
            candidates = cart[index:index + 1]
        elif len(cart) > 1 and context.get("selected_product_id"):
            candidates = [item for item in cart if str(item.get("id")) == str(context["selected_product_id"])]
        if len(candidates) != 1:
            return ("Your cart is empty." if not cart else
                    "Which cart item should I update? " + "; ".join(f"{i + 1}. {item.get('name', item.get('id'))}" for i, item in enumerate(cart)))
        item = candidates[0]
        product = self.search_tool.get_product_by_id(str(item.get("id")))
        if not product:
            return "That product isn't in your cart. Please check the product name or select an item in your cart."
        quantity = int(item.get("quantity", 1))
        if operation == "increase" and not product.get("in_stock"):
            return f"{product['name']} is currently out of stock, so I can't increase its quantity."
        target = 0 if operation == "remove" else max(0, quantity + (1 if operation == "increase" else -1))
        numbers = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
        amount = re.search(r"\b(to|by)\s+(\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten)\b", message, re.I)
        if operation != "remove" and (re.search(r"\b(?:to|by)\s+(?:-\d|\d+\.\d+)", message, re.I) or
                                       (re.search(r"\b(?:to|by)\s+\S+", message, re.I) and not amount)):
            return "Please use a whole-number quantity, such as 'increase the quantity to 2'."
        absolute = bool(amount and amount.group(1).lower() == "to")
        if operation == "set_quantity" and not absolute:
            return "Please specify an absolute quantity, such as 'set the quantity to 1'."
        if amount and operation != "remove":
            value = amount.group(2).lower()
            value = int(value) if value.isdigit() else numbers[value]
            target = value if absolute else max(0, quantity + (value if operation == "increase" else -value))
        if target > quantity and (not product.get("in_stock") or
                                  (product.get("stock") is not None and target > product["stock"])):
            return f"I can't set {product['name']} to {target}; available stock is {product.get('stock', 0)}."
        if amount and operation != "remove":
            operation = "set_quantity"
        command = dict(action=operation, product_id=str(product["id"]), expected_quantity=quantity, quantity=target)
        confirmation = (f"Removed **{product['name']}** from your cart." if target == 0
                        else f"Updated **{product['name']}** to {target} in your cart.")
        return f"[[SHOPAI_CART_ACTION:{json.dumps(command, separators=(',', ':'))}]]{confirmation}"

    @staticmethod
    def _cart_name_tokens(value: str) -> set[str]:
        """Normalize cart references conservatively for catalog-name matching."""
        ignored = {"the", "a", "an", "my", "from", "cart", "product", "item", "please"}
        tokens = set()
        for token in re.findall(r"[a-z0-9]+", value.casefold()):
            if token in ignored:
                continue
            if len(token) > 4 and token.endswith("ies"):
                token = token[:-3] + "y"
            elif len(token) > 3 and token.endswith("s"):
                token = token[:-1]
            tokens.add(token)
        return tokens

    def _comparison_answer(self, message: str, context: Dict[str, Any]) -> str:
        ids = context.get("comparison_product_ids") or context.get("recent_product_ids") or []
        products = [self.search_tool.get_product_by_id(str(pid)) for pid in ids]
        products = [product for product in products if product]
        if re.search(r"\bfirst\s+(?:two|2)\b", message, re.I):
            products = products[:2]
        elif re.search(r"\b(?:these|those|the)\s+(?:two|2)\b", message, re.I) and len(products) > 2:
            return "Which two products should I compare? Choose two from your recent results, for example 'compare the first two products'."
        if len(products) < 2:
            return "I need at least two available products from your recent results to compare. Please choose a search with more options first."
        def cell(value):
            return str(value if value is not None else "Not listed").replace("|", "\\|").replace("\n", " ")
        lines = ["Here is a comparison of your recent results:",
                 "| Field | " + " | ".join(cell(p["name"]) for p in products) + " |",
                 "|---|" + "---|" * len(products)]
        for field, values in [("Brand", [p.get("brand") for p in products]),
                              ("Price", [f"₹{p['price']:,.0f}" for p in products]),
                              ("Stock", ["In Stock" if p.get("in_stock") else "Out of Stock" for p in products])]:
            lines.append("| " + field + " | " + " | ".join(cell(value) for value in values) + " |")
        keys = list(dict.fromkeys(key for p in products for key in (p.get("flattened_specs") or {})))
        for key in keys:
            lines.append("| " + cell(key) + " | " + " | ".join(cell((p.get("flattened_specs") or {}).get(key)) for p in products) + " |")
        if not keys:
            lines.append("\nSpecifications are not listed for these products.")
        if re.search(r"\bbest\s+(?:specifications|specs|features)\b", message, re.I):
            lines.append("\nWhich specification should I use to choose—memory, storage, display, or another feature? I can't rank unlike specifications as an overall best.")
        return "\n".join(lines)

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
            label = " and ".join(filters["category"]) if isinstance(filters.get("category"), list) else {"mobiles": "phone", "headphones": "earphone"}.get(
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
        is_total_query = is_cart_total_query(query)
        if not cart:
            if is_total_query:
                return "Your current cart total is ₹0 for 0 items. Your cart is empty."
            return "Your cart is currently empty. Find a product in the catalog and add it to your cart to see it here."

        total_items = sum(int(item.get("quantity", 1)) for item in cart)
        subtotal = sum(float(item.get("price", 0)) * int(item.get("quantity", 1)) for item in cart)

        query_l = query.lower()
        is_total_query = is_total_query or (any(k in query_l for k in ["total", "how much", "amount", "cost", "value"]) and not any(k in query_l for k in ["show", "items", "what is in", "list"]))

        if is_total_query:
            return f"Your current cart total is {format_inr(subtotal)} for {total_items} item{'s' if total_items != 1 else ''}."

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

    def _ollama_answer(self, message: str, context: Dict[str, Any], timings: Dict[str, Any]) -> str:
        if not settings.OLLAMA_ENABLED:
            timings["ollama_skipped_reason"] = "disabled_by_configuration"
            self._response_source = "deterministic_catalog"
            products = context.get("products") or []
            if products:
                return "\n\n".join(self._format_product_details_answer(product) for product in products)
            self._response_source = "generation_disabled"
            raise HTTPException(status_code=503, detail="Response generation is disabled by configuration.")
        try:
            logger.info("[AI FLOW] OLLAMA CALL: model=%s, url=%s", self.ollama.model, self.ollama.url)
            answer = self.ollama.generate(message, context, timings=timings)
            self._response_source = "ollama"
            logger.info("[AI FLOW] OLLAMA RESPONSE RECEIVED")
            return answer
        except Exception:
            self._response_source = "generation_service_error"
            logger.exception("OLLAMA generation failed")
            products = context.get("products") or []
            if products:
                # Keep the catalog available if local inference is temporarily down.
                self._response_source = "deterministic_catalog_after_generation_error"
                return LLMService._format_products_markdown(message, products)
            raise HTTPException(status_code=503, detail="Response generation is unavailable.")

    async def generate_response(self, request: ChatRequest, timings: Dict[str, Any] | None = None) -> ChatResponse:
        message, incoming = self._request_context(request.message or "")
        session_id = incoming.get("session_id")
        if not isinstance(session_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{16,128}", session_id):
            return await self._generate_response(request, timings)
        now = time.monotonic()
        for key in list(SESSIONS):
            if now - SESSIONS[key]["updated"] > SESSION_TTL and not SESSIONS[key]["lock"].locked():
                del SESSIONS[key]
        if session_id not in SESSIONS:
            if len(SESSIONS) >= SESSION_LIMIT:
                idle = next((key for key, value in SESSIONS.items() if not value["lock"].locked()), None)
                if idle is None:
                    return ChatResponse(response="All chat sessions are busy. Please retry shortly.")
                del SESSIONS[idle]
            SESSIONS[session_id] = {"updated": now, "lock": asyncio.Lock(), "context": {}, "history": []}
        state = SESSIONS[session_id]
        async with state["lock"]:
            self._session = state
            context = dict(state["context"])
            if isinstance(incoming.get("cart"), list):
                context["cart"] = incoming["cart"]
            else:
                context.pop("cart", None)
            if incoming.get("suggestion_product_id"):
                context.update({key: incoming[key] for key in ("suggestion_product_id", "recent_product_ids") if key in incoming})
                context["selected_product_id"] = incoming["suggestion_product_id"]
            # Product-page context must survive answers that do not run a catalog
            # tool; otherwise the next manual question forgets the selected item.
            state["context"] = context
            encoded = message + "\n\n<shopai_client_context>" + json.dumps(context) + "</shopai_client_context>"
            result = await self._generate_response(ChatRequest(message=encoded), timings)
            state["history"] = (state["history"] + [{"user": message[:4000], "assistant": result.response[:12000]}])[-20:]
            state["updated"] = time.monotonic()
            return result

    async def _generate_response(self, request: ChatRequest, timings: Dict[str, Any] | None = None) -> ChatResponse:
        timings = timings if timings is not None else {}
        full_message = (request.message or "").strip()
        user_message, client_context = self._request_context(full_message)
        if not user_message:
            return ChatResponse(response="Please provide a message or question about what you're shopping for.")

        # The configured provider runs once; no automatic model retries/fallback.
        laya_started = time.perf_counter()
        decision_key = "laya" if settings.DECISION_PROVIDER == "laya" else "decision"
        timings[f"{decision_key}_start"] = datetime.now(timezone.utc).isoformat()
        timings["decision_provider"] = settings.DECISION_PROVIDER
        timings["decision_call_count"] = 1
        timings["laya_call_count"] = timings.get("laya_call_count", 0) + (settings.DECISION_PROVIDER == "laya")
        try:
            decision = await run_in_threadpool(self.laya.decide, user_message)
        except Exception:
            timings[f"{decision_key}_end"] = datetime.now(timezone.utc).isoformat()
            timings[f"{decision_key}_duration_ms"] = round((time.perf_counter() - laya_started) * 1000, 1)
            logger.exception("Configured decision provider failed")
            self._response_source = "decision_service_error"
            return ChatResponse(
                response="The configured decision service is unavailable or returned an invalid decision. Please try again shortly."
            )
        timings[f"{decision_key}_end"] = datetime.now(timezone.utc).isoformat()
        timings[f"{decision_key}_duration_ms"] = round((time.perf_counter() - laya_started) * 1000, 1)
        logger.info("CHAT TIMING provider=%s decision_ms=%.1f", settings.DECISION_PROVIDER, timings[f"{decision_key}_duration_ms"])

        laya_choice = decision["choice"]
        timings['predicted_intent'] = laya_choice
        timings['decision_confidence'] = decision.get('confidence')
        timings['decision_probabilities'] = decision.get('probabilities')
        action = laya_choice
        confidence = decision.get("confidence")
        timings["decision_provider"] = decision.get("source", settings.DECISION_PROVIDER)
        logger.info(
            "[AI FLOW] PROVIDER DECISION: choice=%s, confidence=%s, source=%s",
            action, confidence, decision.get("source"),
        )
        logger.info("DECISION action=%s confidence=%s", action, confidence)

        if is_greeting(user_message):
            timings["resolved_action"] = "general_query"
            return ChatResponse(response=await run_in_threadpool(
                self._ollama_answer, user_message,
                {"business": "Poorvika electronics retailer", "greeting": True}, timings,
            ))

        if not re.search(r"\b(?:cart|quantity)\b", user_message, re.I) and re.search(
                r"\bcompare\b|\bbest\s+(?:specifications|specs|features)\b", user_message, re.I):
            timings["resolved_action"] = "comparison"
            self._response_source = "deterministic_comparison"
            logger.info("[AI FLOW] INTENT/ACTION: comparison (provider=%s)", decision.get("source"))
            return ChatResponse(response=self._comparison_answer(user_message, client_context))

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
        cart_view_re = cart_view_re or re.search(r"\bshow\s+me\s+(?:my\s+)?cart\b", user_message, re.I)
        details_re = details_re or re.search(r"\btell\s+me\s+more\s+about\b", user_message, re.I)
        add_to_cart_re = re.search(
            r"^(?:(?:can|could|would)\s+you\s+|i(?:'d|\s+would)?\s+like\s+to\s+|i\s+want\s+to\s+)?(?:please\s+)?(?:add\s+(?:.+?\s+)?to\s+(?:my\s+)?cart|buy\s+(?:it|this)|put\s+.+?\s+in\s+(?:my\s+)?cart|add\s+this\s+phone|add\s+this|add\s+it)\b",
            user_message, re.I
        )
        parsed_cart_operation = parse_cart_operation(user_message)
        cart_operation = parsed_cart_operation["operation"] if parsed_cart_operation else None
        cart_total_query = is_cart_total_query(user_message)
        cart_request = cart_total_query or bool(re.search(r"\b(?:cart|checkout|quantity)\b", user_message, re.I))

        if conversational_re:
            action = "general_query"
        elif cart_operation:
            action = "cart_action"
        elif cart_request and not add_to_cart_re:
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
        # The configured provider ran above; preserve manual search/cart behavior.
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
            and not cart_request and not cart_operation and not cart_view_re and not conversational_re
            and re.search(r"^(?:is|are|does|do|can|could|will|would|how|what|which)\b", user_message, re.I)
        )
        if suggestion_information:
            action = "general_query"
            logger.info("[AI FLOW] SUGGESTION CONTEXT: informational question uses general_query after initial choice %s", laya_choice)

        cheaper_alternative = bool(re.search(r"\bcheaper\s+(?:alternative|option|product|phone)\b", user_message, re.I)) and not cart_request
        cheaper_base = None
        if cheaper_alternative:
            selected_id = client_context.get('selected_product_id')
            cheaper_base = self.search_tool.get_product_by_id(str(selected_id)) if selected_id else suggestion_product
            if not cheaper_base and len(client_context.get('recent_product_ids') or []) == 1:
                cheaper_base = self.search_tool.get_product_by_id(str(client_context['recent_product_ids'][0]))
            if not cheaper_base:
                timings['resolved_action'] = 'product_details'
                return ChatResponse(response="Which product should I find a cheaper alternative to? Choose a product from your recent results first.")
            action = 'product_search'

        discovery_request = re.search(
            r"\b(?:show|find|search|need|want|looking for|do you have|have you got|can i get|available|any)\b",
            user_message, re.I,
        )
        if discovery_request and not cart_request and not suggestion_information and not cart_operation and not cart_view_re and not add_to_cart_re and not details_re and action in (
            "general_query", "cart_action", "product_details"
        ):
            action = "product_search"
            logger.info("[AI FLOW] ACTION RECOVERY: natural product discovery overrides initial choice %s", laya_choice)

        # Laya may classify a bare catalog phrase (for example, "Apple iPhone 15")
        # as a general query or purchase action. Search terms and SQL existence
        # checks below are the deterministic catalog route; only an explicit
        # purchase command may mutate the cart.
        if (
            action in ("general_query", "add_to_cart")
            and not cart_request and not suggestion_information and not conversational_re and not cart_operation and not details_re and not cart_view_re and not add_to_cart_re
        ):
            candidate_filters = self._filters(user_message)
            has_catalog_terms = bool(
                candidate_filters.get("search_term")
                or candidate_filters.get("brand")
                or candidate_filters.get("category")
            )
            if has_catalog_terms:
                general_question = re.search(r"^(?:why|how|what|who|where|when|can|could|would|will|is|are|does|do)\b", user_message, re.I)
                if not general_question or candidate_filters.get("brand") or candidate_filters.get("category"):
                    action = "product_search"
                    logger.info("[AI FLOW] ACTION RECOVERY: catalog phrase overrides initial choice %s", laya_choice)

        previous = client_context.get("search_filters") or {}
        followup = bool(previous and re.search(r"\b(?:only|budget|similar|another|instead)\b", user_message, re.I))
        reference_question = re.search(r"\b(?:its? price|in stock|available in stock|cheapest|cheaper|best specifications)\b", user_message, re.I)
        if reference_question and re.search(r"^(?:what|which|is|are|does|do|how)\b", user_message, re.I) and not add_to_cart_re and not cart_request and not cheaper_alternative:
            action = "product_details"
        elif followup and not add_to_cart_re and not cart_request and not details_re:
            action = client_context.get("search_action", "product_search")
        logger.info("[AI FLOW] INTENT/ACTION: %s (provider=%s initial_choice=%s)", action, decision.get("source"), laya_choice)
        timings["resolved_action"] = action
        logger.info("TOOL/DATABASE action=%s", action)

        if action in ("product_search", "recommendation"):
            extraction_started = time.perf_counter()
            filters = self._filters(user_message, action)
            if followup:
                current = {key: value for key, value in filters.items() if value is not None}
                filters = {**previous, **current}
                budget = re.search(r"\bbudget\D{0,12}(\d[\d,]*(?:\.\d+)?)\s*(k)?", user_message, re.I)
                if budget:
                    filters["max_price"] = float(budget.group(1).replace(",", "")) * (1000 if budget.group(2) else 1)
                    filters["min_price"] = previous.get("min_price")
                    filters["search_term"] = previous.get("search_term")
            if re.search(r"\b(?:available|in stock)\b", user_message, re.I):
                filters["in_stock_only"] = True
            if re.search(r"\b(?:similar|another)\b", user_message, re.I):
                original = self._resolve_product("it", client_context)
                filters["search_term"] = previous.get("search_term")
                filters["exact_name"] = None
                filters["in_stock_only"] = True
                filters["exclude_ids"] = [str(original["id"])] if original else client_context.get("recent_product_ids", [])
                if original:
                    filters["category"] = original.get("category")
                    filters["brand"] = filters.get("brand") or original.get("brand")
                    # Identity terms cannot also be required of an alternative.
                    if filters.get("exact_name") or previous.get("exact_name"):
                        filters["search_term"] = None
            if suggestion_product and re.search(r"\bsimilar\s+products?\b", user_message, re.I):
                filters["search_term"] = None
                filters["category"] = suggestion_product.get("category")
            if cheaper_alternative:
                limit = math.nextafter(float(cheaper_base['price']), -math.inf)
                filters = {**previous, 'category': cheaper_base.get('category'),
                           'brand': previous.get('brand') if previous.get('brand') == cheaper_base.get('brand') else None,
                           'search_term': None, 'exact_name': None, 'min_price': None,
                           'max_price': min(previous.get('max_price') or limit, limit),
                           'exclude_ids': [str(cheaper_base['id'])], 'in_stock_only': True}
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
            if hasattr(self, "_session") and not (cheaper_alternative and not products):
                if products:
                    client_context["comparison_product_ids"] = [str(p["id"]) for p in products]
                client_context.update(search_filters=filters, search_action=action,
                                      recent_product_ids=[str(p["id"]) for p in products], selected_product_id=None)
                self._session["context"] = client_context
            if not products:
                summary = []
                if filters.get("brand"):
                    summary.append(str(filters["brand"]))
                if filters.get("max_price") is not None:
                    summary.append(f"under ₹{filters['max_price']:g}")
                if filters.get("min_price") is not None:
                    summary.append(f"above ₹{filters['min_price']:g}")
                if summary:
                    response += " I kept your request for " + " ".join(summary) + "."
                if filters.get("exclude_ids"):
                    response += " Previously shown products were excluded."
            if filters.get("unmatched_categories"):
                response += " No matches for " + ", ".join(filters["unmatched_categories"]) + " with your current filters."
            if products:
                ids = [str(product["id"]) for product in products]
                response += f"\n\n[[SHOPAI_PRODUCTS:{','.join(ids)}]]"
            logger.info("[AI FLOW] FINAL RESPONSE: source=%s", self._response_source)
            return ChatResponse(response=response)

        if action == "product_details":
            product = self._resolve_product(user_message, client_context)
            if not product:
                choices = [self.search_tool.get_product_by_id(str(pid)) for pid in client_context.get("recent_product_ids", [])]
                choices = [p for p in choices if p]
                if choices and re.search(r"\b(?:cheaper|cheapest)\b", user_message, re.I):
                    minimum = min(p["price"] for p in choices)
                    choices = [p for p in choices if p["price"] == minimum]
                if choices and not self._filters(user_message, "product_details").get("search_term"):
                    return ChatResponse(response="Please choose which of these you mean: " + "; ".join(f"{i + 1}. {p['name']} (₹{p['price']:,.0f})" for i, p in enumerate(choices)))
                return ChatResponse(response="Which product would you like details about? There may be multiple matches; choose one by name or position in the previous results.")
            if hasattr(self, "_session"):
                self._session["context"]["selected_product_id"] = str(product["id"])
            # Format structured, authoritative product details from PostgreSQL catalog without mutating cart
            response = self._format_product_details_answer(product)
            self._response_source = "deterministic_catalog"
            return ChatResponse(response=response + f"\n\n[[SHOPAI_PRODUCTS:{product['id']}]]")

        if action == "add_to_cart":
            product = self._resolve_product(user_message, client_context)
            if not product:
                return ChatResponse(
                    response="Please choose one product by name or position in the previous results, or find it first in the catalog. I need a selected product before changing your cart."
                )
            if not product.get("in_stock"):
                return ChatResponse(response=f"{product['name']} is currently out of stock, so I can't add it to your cart.")
            if hasattr(self, "_session"):
                self._session["context"]["selected_product_id"] = str(product["id"])
            logger.info("CART action=add product_id=%s", product["id"])
            self._response_source = 'cart_command'
            return ChatResponse(
                response=f"[[SHOPAI_PRODUCTS:{product['id']}]][[SHOPAI_ADD_TO_CART:{product['id']}]]Added **{product['name']}** to your cart.\n₹{product['price']:,.0f} • In Stock"
            )

        if action == "cart_action":
            if cart_total_query and not isinstance(client_context.get("cart"), list):
                return ChatResponse(response="I couldn't read your current cart. Open the cart and try again.")
            if not cart_operation and not cart_view_re and not cart_total_query and not re.fullmatch(r"(?:my\s+)?cart[.!?]*", user_message, re.I):
                return ChatResponse(response="I can show your cart, remove an item, or increase/decrease its quantity. Use the cart's Checkout button to place an order.")
            cart = client_context.get("cart")
            if not isinstance(cart, list):
                cart = []
            client_context["cart"] = cart
            response = (self._cart_mutation_answer(user_message, client_context, cart_operation)
                        if cart_operation else self._format_cart_answer(cart, user_message))
            self._response_source = "cart_command" if cart_operation else "cart_state"
            return ChatResponse(response=response)

        context = {"business": "Poorvika electronics retailer", "general_chat": True}
        if suggestion_information:
            context["suggestion_information"] = True
            context["products"] = [{
                key: suggestion_product.get(key)
                for key in ("id", "name", "brand", "category", "price", "in_stock", "flattened_specs", "description")
            }]
        return ChatResponse(response=await run_in_threadpool(self._ollama_answer, user_message, context, timings))
