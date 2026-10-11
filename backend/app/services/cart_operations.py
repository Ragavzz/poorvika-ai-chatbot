"""Parse explicit cart quantity commands without catalog searches or models."""
import re


def parse_cart_operation(message: str):
    removal = re.match(r"^(?:please\s+)?(?:remove|delete)\s+(.+?)\s+from\s+(?:my\s+)?cart\b", message, re.I)
    if removal:
        return {"operation": "remove", "reference": removal.group(1)}
    match = re.match(
        r"^(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?"
        r"(increase|raise|decrease|reduce|lower|set|change|update)\s+(.+?)\s*[.!?]*$",
        message, re.I,
    )
    if not match:
        return None
    verb, body = match.group(1).lower(), match.group(2)
    quantity = re.search(r"\bquantity\b", body, re.I)
    if not quantity:
        return None
    before = body[:quantity.start()].strip()
    after = body[quantity.end():].strip()
    reference = before or re.split(r"\s*\b(?:to|by)\s+", after, maxsplit=1, flags=re.I)[0]
    reference = re.sub(r"^(?:of|for)\s+", "", reference, flags=re.I)
    reference = re.sub(r"^(?:the|my)\s+", "", reference, flags=re.I).strip()
    if reference.lower() in ("the", "my"):
        reference = ""
    reference = re.sub(r"['’]s$", "", reference).strip(" .!?")
    operation = "increase" if verb in ("increase", "raise") else "decrease" if verb in ("decrease", "reduce", "lower") else "set_quantity"
    return {"operation": operation, "reference": reference}
