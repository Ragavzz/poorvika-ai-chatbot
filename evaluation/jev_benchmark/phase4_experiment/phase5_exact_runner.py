"""Run one transparent, sequential full test baseline without retries.

This runner preserves the existing runner and metrics. It adds request/model
telemetry and reports both strict full-test and successful-only accuracy.
"""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from config import DATASET_JSON, DATASET_PARQUET, LAYA_DECIDE_ENDPOINT, LAYA_HEALTH_ENDPOINT, LAYA_REQUEST_TIMEOUT, RESULTS_DIR
from metrics import calculate_brier_score, calculate_ece, calculate_percentile
from runner import parse_laya_decision

EXPECTED_CASES = 400
EXPECTED_DECISIONS = 2000
EXPECTED_TYPES = {"choice": 600, "score": 800, "noul": 600}
WORKFLOWS = (
    "agent_trace_observability",
    "customer_service",
    "invoice_processing",
    "security_incidents",
)
STAMP = "20261004"
PREFIX = os.environ.get("BENCHMARK_RUN_PREFIX", f"phase5_exact_runner_candidate_{STAMP}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def latency_summary(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean_ms": None, "p50_ms": None, "p95_ms": None, "min_ms": None, "max_ms": None}
    return {
        "mean_ms": round(statistics.mean(values), 2),
        "p50_ms": round(calculate_percentile(values, 50), 2),
        "p95_ms": round(calculate_percentile(values, 95), 2),
        "min_ms": round(min(values), 2),
        "max_ms": round(max(values), 2),
    }


def classify_source(body: dict[str, Any] | None) -> str:
    if not isinstance(body, dict):
        return "no_response"
    model = body.get("model")
    source = body.get("source")
    if model == "laya-fallback-router" or source == "laya-calibrated-router":
        return "fallback"
    if model == "laya" and source == "receptron-laya-onnx":
        return "onnx"
    if model == "laya" and source == "official-python-laya":
        return "typed_decisions"
    return "unknown"


def make_summary(
    cases: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    case_latencies: list[float],
    case_success: list[bool],
    source_counts: Counter[str],
    started: str,
    dataset_hashes_before: dict[str, str],
) -> dict[str, Any]:
    by_type: dict[str, Any] = {}
    for decision_type in ("choice", "score", "noul"):
        rows = [row for row in decisions if row["decision_type"] == decision_type]
        valid = [row for row in rows if row["prediction_success"]]
        correct = sum(bool(row["correct"]) for row in valid)
        result: dict[str, Any] = {
            "expected": len(rows),
            "successful": len(valid),
            "failed": len(rows) - len(valid),
            "correct": correct,
            "strict_accuracy": correct / len(rows) if rows else 0.0,
            "successful_only_accuracy": correct / len(valid) if valid else 0.0,
        }
        if decision_type == "score":
            errors = [row["score_error"] for row in valid if row.get("score_error") is not None]
            result["mae"] = statistics.mean(errors) if errors else None
        by_type[decision_type] = result

    by_workflow: dict[str, Any] = {}
    for workflow in WORKFLOWS:
        rows = [row for row in decisions if row["workflow"] == workflow]
        valid = [row for row in rows if row["prediction_success"]]
        correct = sum(bool(row["correct"]) for row in valid)
        by_workflow[workflow] = {
            "expected": len(rows),
            "successful": len(valid),
            "failed": len(rows) - len(valid),
            "correct": correct,
            "strict_accuracy": correct / len(rows) if rows else 0.0,
            "successful_only_accuracy": correct / len(valid) if valid else 0.0,
        }

    valid_decisions = [row for row in decisions if row["prediction_success"]]
    correct = sum(bool(row["correct"]) for row in valid_decisions)
    successful = len(valid_decisions)
    failed = len(decisions) - successful
    successful_cases = [lat for lat, ok in zip(case_latencies, case_success) if ok]
    failed_cases = [lat for lat, ok in zip(case_latencies, case_success) if not ok]
    dataset_hashes_after = {str(path.name): sha256(path) for path in (DATASET_JSON, DATASET_PARQUET)}

    return {
        "benchmark": "LocalLLaMA/typed-decisions",
        "split": "test",
        "model_configuration": "convaiinnovations/laya via @receptron/laya 0.1.2",
        "endpoint": LAYA_DECIDE_ENDPOINT,
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "request_policy": {"sequential": True, "retries": 0, "timeout_seconds": LAYA_REQUEST_TIMEOUT},
        "expected_cases": len(cases),
        "expected_decisions": len(decisions),
        "expected_by_type": EXPECTED_TYPES,
        "successful_decisions": successful,
        "failed_decisions": failed,
        "success_rate": successful / len(decisions) if decisions else 0.0,
        "correct_predictions": correct,
        "strict_full_test_accuracy": correct / len(decisions) if decisions else 0.0,
        "successful_only_accuracy": correct / successful if successful else 0.0,
        "choice_accuracy": by_type["choice"]["strict_accuracy"],
        "score_accuracy": by_type["score"]["strict_accuracy"],
        "noul_accuracy": by_type["noul"]["strict_accuracy"],
        "brier_soft_gold_successful_predictions": calculate_brier_score(valid_decisions),
        "ece_successful_predictions": calculate_ece(valid_decisions),
        "score_mae_successful_predictions": by_type["score"]["mae"],
        "by_type": by_type,
        "by_workflow": by_workflow,
        "latency_ms": {
            "all_cases": latency_summary(case_latencies),
            "successful_cases": latency_summary(successful_cases),
            "failed_cases": latency_summary(failed_cases),
        },
        "request_outcomes": dict(source_counts),
        "dataset_sha256_before": dataset_hashes_before,
        "dataset_sha256_after": dataset_hashes_after,
        "dataset_unchanged": dataset_hashes_before == dataset_hashes_after,
    }


def render_report(summary: dict[str, Any], failures: list[dict[str, Any]]) -> str:
    lines = [
        "# LocalLLaMA typed-decisions â€” Baseline v2",
        "",
        f"- Started: `{summary['started_at']}`",
        f"- Finished: `{summary['finished_at']}`",
        f"- Model configuration: `{summary['model_configuration']}`",
        f"- Endpoint: `{summary['endpoint']}`",
        f"- Requests: sequential, retries disabled, timeout {summary['request_policy']['timeout_seconds']} seconds",
        "",
        "## Overall",
        "",
        "| Measure | Result |",
        "|---|---:|",
        f"| Expected cases | {summary['expected_cases']} |",
        f"| Expected decisions | {summary['expected_decisions']} |",
        f"| Successful decisions | {summary['successful_decisions']} |",
        f"| Failed decisions | {summary['failed_decisions']} |",
        f"| Success rate | {summary['success_rate']:.4%} |",
        f"| Correct predictions | {summary['correct_predictions']} |",
        f"| Strict full-test accuracy | {summary['strict_full_test_accuracy']:.4%} |",
        f"| Successful-only accuracy | {summary['successful_only_accuracy']:.4%} |",
        f"| Brier (soft gold, successful predictions) | {summary['brier_soft_gold_successful_predictions']:.6f} |",
        f"| ECE (successful predictions) | {summary['ece_successful_predictions']:.6f} |",
        f"| Score MAE (successful score predictions) | {summary['score_mae_successful_predictions']} |",
        "",
        "## Decision types",
        "",
        "| Type | Expected | Successful | Failed | Correct | Strict accuracy | Successful-only accuracy | MAE |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for kind in ("choice", "score", "noul"):
        row = summary["by_type"][kind]
        mae = "â€”" if row.get("mae") is None else f"{row['mae']:.6f}"
        lines.append(
            f"| {kind} | {row['expected']} | {row['successful']} | {row['failed']} | {row['correct']} | "
            f"{row['strict_accuracy']:.4%} | {row['successful_only_accuracy']:.4%} | {mae} |"
        )
    lines += ["", "## Workflows", "", "| Workflow | Expected | Successful | Failed | Correct | Strict accuracy | Successful-only accuracy |", "|---|---:|---:|---:|---:|---:|---:|"]
    for workflow, row in summary["by_workflow"].items():
        lines.append(
            f"| {workflow} | {row['expected']} | {row['successful']} | {row['failed']} | {row['correct']} | "
            f"{row['strict_accuracy']:.4%} | {row['successful_only_accuracy']:.4%} |"
        )
    lines += [
        "",
        "## Latency (case-level; each case counted once)",
        "",
        "| Set | Mean ms | P50 ms | P95 ms | Min ms | Max ms |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, key in (("All", "all_cases"), ("Successful", "successful_cases"), ("Failed", "failed_cases")):
        latency = summary["latency_ms"][key]
        values = ["â€”" if latency[k] is None else f"{latency[k]:.2f}" for k in ("mean_ms", "p50_ms", "p95_ms", "min_ms", "max_ms")]
        lines.append(f"| {label} | " + " | ".join(values) + " |")
    lines += [
        "",
        "## Model/source validation",
        "",
        f"- ONNX responses: {summary['request_outcomes'].get('onnx', 0)}",
        f"- Fallback responses: {summary['request_outcomes'].get('fallback', 0)}",
        f"- Unknown model/source responses: {summary['request_outcomes'].get('unknown', 0)}",
        f"- Requests without a valid response: {summary['request_outcomes'].get('no_response', 0)}",
        f"- Failed decision rows: {len(failures)} (see failure log)",
        f"- Test dataset unchanged by SHA-256: {summary['dataset_unchanged']}",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="required confirmation to run the full 400-case test split")
    args = parser.parse_args()
    if not args.full:
        parser.error("this baseline runner only supports the full benchmark; pass --full")

    cases = json.loads(DATASET_JSON.read_text(encoding="utf-8"))
    decision_count = sum(len(case["questions"]) for case in cases)
    actual_types = Counter(question["type"] for case in cases for question in case["questions"].values())
    if len(cases) != EXPECTED_CASES or decision_count != EXPECTED_DECISIONS or dict(actual_types) != EXPECTED_TYPES:
        raise RuntimeError(f"Dataset shape changed; refusing run: cases={len(cases)}, decisions={decision_count}, types={dict(actual_types)}")

    out_paths = {
        "raw": RESULTS_DIR / f"{PREFIX}_raw.jsonl",
        "summary": RESULTS_DIR / f"{PREFIX}_summary.json",
        "report": RESULTS_DIR / f"{PREFIX}_report.md",
        "failures": RESULTS_DIR / f"{PREFIX}_failures.jsonl",
    }
    existing = [str(path) for path in out_paths.values() if path.exists()]
    if existing:
        raise FileExistsError("Refusing to overwrite baseline artifacts: " + ", ".join(existing))

    hashes_before = {str(path.name): sha256(path) for path in (DATASET_JSON, DATASET_PARQUET)}
    with requests.Session() as session:
        health = session.get(LAYA_HEALTH_ENDPOINT, timeout=10)
        health.raise_for_status()
        health_json = health.json()
        if not health_json.get("laya_loaded"):
            raise RuntimeError(f"Laya is not loaded; benchmark not started: {health_json}")
        print("HEALTH", json.dumps(health_json), flush=True)

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        decisions: list[dict[str, Any]] = []
        case_latencies: list[float] = []
        case_success: list[bool] = []
        source_counts: Counter[str] = Counter()
        failures: list[dict[str, Any]] = []
        started_at = datetime.now(timezone.utc).isoformat()

        with out_paths["raw"].open("x", encoding="utf-8") as raw_stream:
            for index, case in enumerate(cases, start=1):
                request_started = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
                timer = time.perf_counter()
                status = None
                body = None
                response_text = None
                request_error = None
                try:
                    response = session.post(
                        LAYA_DECIDE_ENDPOINT,
                        json={"state": case["state"], "questions": case["questions"]},
                        timeout=LAYA_REQUEST_TIMEOUT,
                    )
                    status = response.status_code
                    response_text = response.text if status != 200 else None
                    if status == 200:
                        body = response.json()
                        if not isinstance(body, dict):
                            request_error = "malformed response: top-level JSON must be an object"
                        elif not isinstance(body.get("answers"), dict):
                            request_error = "malformed response: answers must be an object"
                    else:
                        request_error = f"HTTP {status}: {(response.text or '')[:500]}"
                except requests.Timeout as exc:
                    request_error = f"timeout: {exc!r}"
                except ValueError as exc:
                    request_error = f"malformed JSON: {exc!r}"
                except requests.RequestException as exc:
                    request_error = f"transport: {exc!r}"
                except Exception as exc:
                    request_error = f"unexpected request error: {exc!r}"

                ended = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
                latency_ms = round((time.perf_counter() - timer) * 1000.0, 2)
                case_latencies.append(latency_ms)
                source_kind = classify_source(body)
                if status == 200 and body is not None:
                    source_counts[source_kind] += 1
                else:
                    source_counts["no_response"] += 1
                answers = (body.get("answers") or {}) if isinstance(body, dict) else {}
                case_decisions: list[dict[str, Any]] = []
                for question_id, spec in case["questions"].items():
                    answer = answers.get(question_id) if request_error is None else None
                    row = parse_laya_decision(question_id, spec, case["gold"].get(question_id, {}), answer)
                    row["case_id"] = case["case_id"]
                    row["workflow"] = case["workflow"]
                    row["question"] = spec
                    row["state"] = case["state"]
                    row["raw_answer"] = answer
                    row["request_status"] = status
                    row["request_error"] = request_error
                    row["latency_ms"] = latency_ms
                    row["model"] = (body or {}).get("model") if isinstance(body, dict) else None
                    row["source"] = (body or {}).get("source") if isinstance(body, dict) else None
                    if request_error and not row.get("error"):
                        row["error"] = request_error
                    if row.get("pred_label") in (None, "") and not row.get("error"):
                        row["error"] = "missing prediction"
                    row["prediction_success"] = row.get("error") is None and row.get("pred_label") not in (None, "")
                    decisions.append(row)
                    case_decisions.append(row)

                case_ok = all(row["prediction_success"] for row in case_decisions)
                case_success.append(case_ok)
                raw_record = {
                    "case_id": case["case_id"],
                    "workflow": case["workflow"],
                    "request_start_utc": request_started,
                    "request_end_utc": ended,
                    "latency_ms": latency_ms,
                    "http_status": status,
                    "request_error": request_error,
                    "response_received": body is not None,
                    "model": (body or {}).get("model") if isinstance(body, dict) else None,
                    "source": (body or {}).get("source") if isinstance(body, dict) else None,
                    "source_class": source_kind,
                    "retry_count": 0,
                    "state": case["state"],
                    "questions": case["questions"],
                    "gold": case["gold"],
                    "response": body,
                    "response_error_text": response_text,
                    "case_success": case_ok,
                    "decisions": case_decisions,
                }
                raw_stream.write(json.dumps(raw_record, ensure_ascii=False) + "\n")
                raw_stream.flush()
                # Keep the full case in the JSONL artifact, but release it from
                # the in-memory score rows; the summary scorer needs only labels,
                # probabilities, confidence, and timing.
                for scored_row in case_decisions:
                    scored_row.pop("state", None)
                    scored_row.pop("question", None)
                    scored_row.pop("raw_answer", None)
                if not case_ok:
                    failures.append(raw_record)

                if index % 10 == 0 or index == len(cases):
                    success_count = sum(row["prediction_success"] for row in decisions)
                    correct_count = sum(row["prediction_success"] and bool(row["correct"]) for row in decisions)
                    print(
                        f"PROGRESS cases={index}/{len(cases)} decisions={len(decisions)}/{decision_count} "
                        f"successful={success_count} failed={len(decisions)-success_count} correct={correct_count} "
                        f"last_case={case['case_id']} latency_ms={latency_ms} source={source_kind}",
                        flush=True,
                    )

    summary = make_summary(cases, decisions, case_latencies, case_success, source_counts, started_at, hashes_before)
    with out_paths["failures"].open("x", encoding="utf-8") as stream:
        for failure in failures:
            stream.write(json.dumps(failure, ensure_ascii=False) + "\n")
    out_paths["summary"].write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out_paths["report"].write_text(render_report(summary, failures), encoding="utf-8")
    print("FINAL_SUMMARY", json.dumps(summary, ensure_ascii=False), flush=True)
    print("ARTIFACTS", json.dumps({key: str(value) for key, value in out_paths.items()}), flush=True)


if __name__ == "__main__":
    main()



