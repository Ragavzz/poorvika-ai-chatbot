"""Client for the local Laya System-1 decision service."""

import logging
from typing import Any, Dict

import requests

from app.config import settings

logger = logging.getLogger("shopai.services.laya")
HTTP = requests.Session()

POORVIKA_ACTIONS = [
    "product_search",
    "product_details",
    "recommendation",
    "add_to_cart",
    "cart_action",
    "general_query",
]


class LayaClient:
    """Ask the running official Laya service to choose a business action."""

    def __init__(self) -> None:
        self.url = settings.LAYA_DECIDE_URL
        self.timeout = 60

    def decide(self, message: str) -> Dict[str, Any]:
        logger.info("LAYA request: %s", message)
        response = HTTP.post(
            self.url,
            # server.js expects a state object and reads `state.message`; Laya
            # serializes this structured state differently from a bare string.
            # Its configured question/options are supplied by the service.
            json={"state": {"message": message}},
            timeout=self.timeout,
        )
        response.raise_for_status()
        result = response.json()
        # The external server has a regex fallback router. Never let that stand
        # in for the requested System-1 model in the active chat path.
        if result.get("source") != "receptron-laya-onnx" or result.get("model") == "laya-fallback-router":
            raise RuntimeError("The Laya ONNX model is unavailable; refusing its fallback router")
        answer = (result.get("answers") or {}).get("intent") or {}
        if answer.get("type") != "choice" or answer.get("choice") not in POORVIKA_ACTIONS:
            raise ValueError("Laya returned an unknown or missing action choice")

        decision = {
            "choice": answer["choice"],
            "probabilities": answer.get("probabilities", {}),
            "confidence": answer.get("confidence"),
            "noul": (result.get("answers") or {}).get("needs_escalation", {}).get("noul"),
            "source": result.get("source"),
        }
        logger.info(
            "LAYA decision: choice=%s confidence=%s probabilities=%s noul=%s",
            decision["choice"], decision["confidence"], decision["probabilities"], decision["noul"],
        )
        return decision
