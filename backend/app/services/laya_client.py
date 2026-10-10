"""Client for the isolated Laya V2 System-1 decision service."""

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict

import requests

from app.config import settings

logger = logging.getLogger("shopai.services.laya")
HTTP = requests.Session()

POORVIKA_ACTIONS = {
    "product_search",
    "product_details",
    "recommendation",
    "add_to_cart",
    "cart_action",
    "general_query",
}

PROJECT_ROOT = Path(__file__).resolve().parents[3]
QUESTIONS_FILE = PROJECT_ROOT / "laya_v2_service" / "shopai_questions.json"


class LayaClient:
    """Call Laya V2 and validate its genuine model decision."""

    def __init__(self) -> None:
        self.url = settings.LAYA_DECIDE_URL
        self.timeout = 60

        with QUESTIONS_FILE.open("r", encoding="utf-8") as file:
            self.questions = json.load(file)

    def decide(self, message: str) -> Dict[str, Any]:
        logger.info("LAYA V2 request: %s", message)

        response = HTTP.post(
            self.url,
            json={
                "state": {"message": message},
                "questions": self.questions,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        result = response.json()

        if not isinstance(result, dict):
            raise ValueError("Laya V2 response must be an object")

        if result.get("model") != "Mass121/laya-typed-decisions-v2":
            raise RuntimeError("Unexpected Laya V2 model identity")

        answers = result.get("answers")
        if not isinstance(answers, dict):
            raise ValueError("Laya V2 returned no answers object")
        answer = answers.get("intent")
        if not isinstance(answer, dict):
            raise ValueError("Laya V2 returned no intent object")

        if answer.get("type") != "choice":
            raise ValueError("Laya V2 returned no valid intent choice")

        choice = answer.get("choice")
        if not isinstance(choice, str) or choice not in POORVIKA_ACTIONS:
            raise ValueError(f"Unknown Laya V2 action: {choice!r}")

        probabilities = answer.get("probabilities")
        if not isinstance(probabilities, dict) or set(probabilities) != POORVIKA_ACTIONS:
            raise ValueError("Laya V2 returned an invalid probability distribution")
        def probability(value):
            return (isinstance(value, (int, float)) and not isinstance(value, bool)
                    and math.isfinite(value) and 0 <= value <= 1)
        if not all(probability(value) for value in probabilities.values()):
            raise ValueError("Laya V2 returned invalid probabilities")
        # The service rounds probabilities to four decimal places.
        if not math.isclose(sum(probabilities.values()), 1.0, abs_tol=0.001):
            raise ValueError("Laya V2 probabilities do not sum to one")
        if not probability(answer.get("confidence")):
            raise ValueError("Laya V2 returned invalid confidence")
        answer_confidence = answer.get("answer_confidence")
        if answer_confidence is not None and not probability(answer_confidence):
            raise ValueError("Laya V2 returned invalid answer confidence")

        decision = {
            "choice": choice,
            "probabilities": probabilities,
            "confidence": answer.get("confidence"),
            "answer_confidence": answer_confidence,
            "action": answer.get("action"),
            "noul": answers.get("needs_escalation"),
            "source": "laya-python-v2",
        }

        logger.info(
            "LAYA V2 decision: choice=%s confidence=%s",
            decision["choice"],
            decision["confidence"],
        )
        return decision
