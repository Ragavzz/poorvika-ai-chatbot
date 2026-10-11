"""Explicit lightweight demo provider; no model imports or network requests."""

import re

from app.config import settings
from app.services.cart_queries import is_cart_total_query
from app.services.cart_operations import parse_cart_operation


def is_greeting(message: str) -> bool:
    """Match complete greetings, never a product request prefixed with hello."""
    return bool(re.fullmatch(
        r"(?:hi|hello|hey|good\s+(?:morning|afternoon|evening))[\s.!?]*",
        message.strip(), re.I,
    ))


class RuleDecisionProvider:
    def decide(self, message):
        text = message.lower().strip()
        if parse_cart_operation(text) or is_cart_total_query(text):
            choice = "cart_action"
        elif re.search(r"\b(?:cart|checkout|quantity)\b", text) or re.match(r"(?:please\s+)?(?:buy|add|put)\b", text):
            choice = "add_to_cart" if re.search(r"\b(?:add|buy|put)\b", text) else "cart_action"
        elif re.search(r"\b(?:compare|details|specs|specifications|features|price|stock|cheapest|cheaper)\b|tell\s+me\s+(?:more\s+)?about", text):
            choice = "product_details"
        elif re.search(r"\b(?:recommend|suggest|best)\b", text):
            choice = "recommendation"
        elif re.search(r"\b(?:show|find|search|similar|another|only|budget|looking|need|want)\b", text):
            choice = "product_search"
        else:
            choice = "general_query"
        return {"choice": choice, "source": "rule-based", "confidence": None}


def create_decision_provider():
    if settings.DECISION_PROVIDER == "rules":
        return RuleDecisionProvider()
    from app.services.laya_client import LayaClient
    return LayaClient()
