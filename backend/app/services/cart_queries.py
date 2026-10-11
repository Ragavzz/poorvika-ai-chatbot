"""Shared recognition for deterministic cart totals, without model dependencies."""
import re

TOTAL_QUERY = re.compile(
    r"\b(?:my|the)\s+(?:(?:current|updated|cart|grand)\s+)*(?:total|subtotal)\b"
    r"|\b(?:current|updated)\s+(?:cart\s+)?total\b"
    r"|\b(?:total(?:\s+(?:price|cost|amount))?|subtotal)\s+(?:of|for)\s+"
    r"(?:all\s+)?(?:(?:my|the|cart)\s+)?items\b"
    r"|\bhow\s+much\s+(?:do\s+i\s+owe|(?:is|does)\s+(?:my|the)\s+cart(?:\s+cost)?)\b"
    r"|\bcart\s+(?:total|subtotal|amount|value|cost)\b",
    re.I,
)


def is_cart_total_query(message: str) -> bool:
    return bool(TOTAL_QUERY.search(message))


def format_inr(amount: float) -> str:
    """Indian grouping, retaining paise when present."""
    value = f"{amount:.2f}"
    whole, decimal = value.split('.')
    sign = '-' if whole.startswith('-') else ''
    digits = whole.lstrip('-')
    if len(digits) > 3:
        prefix, last = digits[:-3], digits[-3:]
        groups = []
        while prefix:
            groups.insert(0, prefix[-2:])
            prefix = prefix[:-2]
        digits = ','.join([*groups, last])
    return f"₹{sign}{digits}" + (f".{decimal}" if decimal != '00' else '')
