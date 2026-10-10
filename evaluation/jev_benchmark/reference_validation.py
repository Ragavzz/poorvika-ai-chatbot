"""Independent, offline decoder audit for the saved LocalLLaMA baseline.

This reads saved outputs only. It never contacts the Laya service and never
uses expected labels to produce a decoded prediction.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
INCORRECT = RESULTS / "ERROR_ANALYSIS_V2_incorrect_decisions.jsonl"
RAW = RESULTS / "baseline_v2_20261004_raw.jsonl"
OUT = RESULTS / "PHASE3_REFERENCE_VALIDATION.jsonl"


def reference_decode(kind: str, spec: dict[str, Any], answer: dict[str, Any] | None) -> dict[str, Any]:
    """Decode directly from the recorded response with independent operations."""
    answer = answer if isinstance(answer, dict) else {}
    p = answer.get("probabilities")
    probs = p if isinstance(p, dict) else {}
    result: dict[str, Any] = {"label": None, "score": None, "probabilities": probs,
                              "confidence": answer.get("confidence"), "decision_probability": None}
    if kind == "choice":
        if not probs:
            return result
        # Stable alphabetical tie-break is explicit and independent of dict order.
        result["label"] = sorted(probs.items(), key=lambda pair: (-float(pair[1]), str(pair[0])))[0][0]
        if result["confidence"] is None:
            result["confidence"] = max(float(v) for v in probs.values())
    elif kind == "score":
        if probs:
            result["label"] = sorted(probs.items(), key=lambda pair: (-float(pair[1]), int(pair[0])))[0][0]
        raw_score = answer.get("score")
        result["score"] = float(raw_score) if raw_score is not None else None
        if result["confidence"] is None and probs:
            result["confidence"] = max(float(v) for v in probs.values())
    elif kind == "noul":
        value = answer.get("noul")
        if value is not None:
            p_true = float(value)
            result["decision_probability"] = p_true
            result["probabilities"] = {"true": p_true, "false": 1.0 - p_true}
            result["label"] = "true" if p_true >= 0.5 else "false"
            result["confidence"] = max(p_true, 1.0 - p_true)
    return result


def mapping_issue(kind: str, spec: dict[str, Any], answer: dict[str, Any]) -> str | None:
    criteria = spec.get("criteria")
    probs = answer.get("probabilities") or {}
    if kind == "choice" and isinstance(criteria, dict):
        if set(criteria) != set(probs):
            return "choice probability keys do not match named options"
        if answer.get("choice") is not None and answer.get("choice") not in criteria:
            return "returned choice is not a declared option"
        winner = sorted(probs.items(), key=lambda pair: (-float(pair[1]), str(pair[0])))[0][0] if probs else None
        if answer.get("choice") is not None and winner != answer.get("choice"):
            return "returned choice differs from probability winner"
    if kind == "score" and isinstance(criteria, list):
        legend = answer.get("legend") or {}
        expected_legend = {str(i): label for i, label in enumerate(criteria)}
        if legend != expected_legend or set(probs) != set(expected_legend):
            return "score legend/index mapping differs from declared rubric"
        if probs:
            winner = sorted(probs.items(), key=lambda pair: (-float(pair[1]), int(pair[0])))[0][0]
            expected_score = sum(int(k) * float(v) for k, v in probs.items())
            if str(winner) not in probs or abs(float(answer.get("score", expected_score)) - expected_score) > 0.001:
                return "score label/expected-value decoding discrepancy"
    return None


def main() -> None:
    with INCORRECT.open(encoding="utf-8") as stream:
        incorrect = [json.loads(line) for line in stream if line.strip()]
    raw_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    with RAW.open(encoding="utf-8") as stream:
        for line in stream:
            case = json.loads(line)
            for decision in case.get("decisions", []):
                raw_by_key[(case["case_id"], decision["question_id"])] = {
                    "case": case, "decision": decision,
                    "answer": (case.get("response", {}).get("answers", {}) or {}).get(decision["question_id"]),
                }

    counts = Counter()
    with OUT.open("w", encoding="utf-8", newline="\n") as stream:
        for old in incorrect:
            case_id, qid = old["case_id"], old["question_id"]
            joined = raw_by_key.get((case_id, qid))
            if not joined:
                raise RuntimeError(f"Missing raw baseline row: {case_id}/{qid}")
            case, prod, answer = joined["case"], joined["decision"], joined["answer"] or {}
            kind = old["decision_type"]
            ref = reference_decode(kind, case["questions"][qid], answer)
            expected = old["expected_output"]["label"]
            prod_label = prod.get("pred_label")
            flags = old.get("input_audit_flags") or []
            issue = mapping_issue(kind, case["questions"][qid], answer)

            # Attribute only demonstrable integration defects. Input parity flags
            # are association, so remain unresolved without a replay experiment.
            if not ref.get("label") or str(ref["label"]) != str(prod_label):
                category, bucket = "adapter/decoder error", "adapter/integration"
            elif issue:
                category, bucket = ("choice option-ordering/mapping error" if kind == "choice" else
                                    "score decoding/mapping error"), "adapter/integration"
            elif flags:
                category, bucket = "input/serialization issue (causality unproven)", "unresolved"
            else:
                category, bucket = "genuine Laya model error", "model-side"
            counts[bucket] += 1
            raw_conf = answer.get("confidence")
            row = {
                "case_id": case_id, "question_id": qid, "workflow": old["workflow"],
                "decision_type": kind, "expected": expected,
                "raw_laya_output": answer,
                "production_decoded_output": {"label": prod_label, "score": prod.get("pred_score"),
                    "probabilities": prod.get("pred_probabilities"), "confidence": prod.get("confidence")},
                "independent_reference_decoded_output": ref,
                "error_category": category, "attribution_bucket": bucket,
                "confidence_probability_information": {
                    "raw_confidence": raw_conf, "raw_probabilities": answer.get("probabilities"),
                    "noul_probability_true": answer.get("noul") if kind == "noul" else None,
                    "probability_sum": (sum(float(v) for v in answer["probabilities"].values())
                                        if isinstance(answer.get("probabilities"), dict) else None),
                },
                "input_audit_flags": flags,
                "mapping_audit": issue,
                "attribution_note": ("Saved input parity flag; its causal effect is not identifiable without rerunning inference."
                                     if flags and bucket == "unresolved" else
                                     "Independent decoding agrees with production; recorded output disagrees with gold."
                                     if bucket == "model-side" else "Independent decode did not validate production output."),
            }
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    summary = {"analyzed_incorrect_decisions": len(incorrect),
               "adapter_integration_errors": counts["adapter/integration"],
               "model_side_errors": counts["model-side"], "unresolved": counts["unresolved"],
               "sum_check": sum(counts[k] for k in ("adapter/integration", "model-side", "unresolved")),
               "output": OUT.name}
    (RESULTS / "PHASE3_REFERENCE_VALIDATION_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
