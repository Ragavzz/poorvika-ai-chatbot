"""V2 adapter contract tests; no live model or database required."""
import copy
import unittest
from unittest.mock import Mock, patch
from app.services.laya_client import LayaClient, POORVIKA_ACTIONS

class LayaContractTests(unittest.TestCase):
    def setUp(self):
        self.client = LayaClient()
        self.body = {"model": "Mass121/laya-typed-decisions-v2", "answers": {"intent": {
            "type": "choice", "choice": "product_search", "confidence": 0.96,
            "answer_confidence": 0.9885, "probabilities": {action: (0.9885 if action == "product_search" else 0.0023) for action in POORVIKA_ACTIONS},
            "action": {"act_probability": 1}}}}

    def call(self, body):
        response = Mock()
        response.json.return_value = body
        with patch("app.services.laya_client.HTTP.post", return_value=response):
            return self.client.decide("Show phones")

    def test_preserves_distinct_model_confidences(self):
        result = self.call(self.body)
        self.assertEqual(result["confidence"], 0.96)
        self.assertEqual(result["answer_confidence"], 0.9885)
        self.assertEqual(result["probabilities"], self.body["answers"]["intent"]["probabilities"])

    def test_rejects_wrong_model_and_missing_or_malformed_decision(self):
        for body in [[], None, {}, {"model": "laya-fallback-router"}, {"model": self.body["model"], "answers": []}, {"model": self.body["model"], "answers": {"intent": []}}]:
            with self.subTest(body=body), self.assertRaises((ValueError, RuntimeError)):
                self.call(body)

    def test_rejects_unsupported_action_and_invalid_numeric_fields(self):
        mutations = [("choice", "checkout"), ("confidence", None), ("confidence", True), ("confidence", float("nan")), ("confidence", 1.1), ("answer_confidence", -1), ("probabilities", {}), ("probabilities", {key: 0.5 for key in POORVIKA_ACTIONS}), ("probabilities", {key: float("inf") for key in POORVIKA_ACTIONS})]
        for field, value in mutations:
            body = copy.deepcopy(self.body)
            body["answers"]["intent"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.call(body)

if __name__ == "__main__":
    unittest.main()
