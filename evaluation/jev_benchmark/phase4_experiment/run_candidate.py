"""Offline experiment runner for the official fine-tuned Laya checkpoint.

Uses the same dataset fields, production decision parser, and metric helpers as
the saved baseline runner. The full test run requires an explicit --full flag.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(HERE))

import run_baseline_v2 as baseline
from runner import parse_laya_decision

DATASET = BENCH / "dataset" / "typed_decisions_test.json"
BASELINE_RAW = BENCH / "results" / "baseline_v2_20261004_raw.jsonl"
RESULTS = BENCH / "results"
MODEL_ID = "convaiinnovations/laya-typed-decisions"
PREFIX = "phase4_typed_decisions_candidate_20261004"
os.environ.setdefault("USE_TF", "0")


def load_model():
    import laya
    from laya import PINNED_REVISIONS
    revision = PINNED_REVISIONS[MODEL_ID]
    agent = laya.load(MODEL_ID, revision=revision, device="cpu")
    return agent


def model_answers(agent: Any, state: dict[str, Any], questions: dict[str, Any]) -> dict[str, Any]:
    output = agent.predict(state, questions)
    if not isinstance(output, dict):
        raise TypeError(f"Laya predict returned {type(output).__name__}, expected object")
    answers = output.get("answers", output)
    if not isinstance(answers, dict):
        raise TypeError("Laya predict output has no answer object")
    return answers


def read_baseline_by_case() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    by_case: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    with BASELINE_RAW.open(encoding="utf-8") as stream:
        for line in stream:
            case = json.loads(line)
            by_case[case["case_id"]] = case
            rows.extend(case.get("decisions", []))
    return by_case, rows


def run(pilot: bool, full: bool) -> None:
    all_cases = json.loads(DATASET.read_text(encoding="utf-8"))
    if pilot:
        by_workflow: dict[str, list[dict[str, Any]]] = {}
        for item in all_cases:
            by_workflow.setdefault(item["workflow"], []).append(item)
        cases = [case for workflow in sorted(by_workflow) for case in by_workflow[workflow][:10]]
    else:
        cases = all_cases
    if not full and not pilot:
        raise ValueError("provide --pilot for validation or --full for the complete benchmark")
    if full and len(cases) != 400:
        raise ValueError(f"full mode requires all 400 cases, got {len(cases)}")

    baseline_by_case, _ = read_baseline_by_case()
    started = datetime.now(timezone.utc).isoformat()
    agent = load_model()
    candidate_decisions: list[dict[str, Any]] = []
    latencies: list[float] = []
    failures: list[dict[str, Any]] = []
    output_path = RESULTS / f"{PREFIX}_{'full' if full else 'pilot'}_raw.jsonl"
    summary_path = RESULTS / f"{PREFIX}_{'full' if full else 'pilot'}_summary.json"
    report_path = RESULTS / f"{PREFIX}_{'full' if full else 'pilot'}_report.md"
    if any(path.exists() for path in (output_path, summary_path, report_path)):
        raise FileExistsError("Refusing to overwrite an existing Phase 4 result")

    with output_path.open("x", encoding="utf-8", newline="\n") as stream:
        for index, case in enumerate(cases, 1):
            start = time.perf_counter()
            request_error = None
            answer_map: dict[str, Any] = {}
            try:
                answer_map = model_answers(agent, case["state"], case["questions"])
            except Exception as exc:
                request_error = f"{type(exc).__name__}: {exc}"
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            latencies.append(elapsed_ms)
            case_decisions: list[dict[str, Any]] = []
            for qid, spec in case["questions"].items():
                raw_answer = answer_map.get(qid) if not request_error else None
                row = parse_laya_decision(qid, spec, case["gold"].get(qid, {}), raw_answer)
                row.update({"case_id": case["case_id"], "workflow": case["workflow"],
                            "question": spec, "state": case["state"], "raw_answer": raw_answer,
                            "request_status": 200 if request_error is None else None,
                            "request_error": request_error, "latency_ms": elapsed_ms,
                            "model": MODEL_ID, "source": "official-python-laya",
                            "prediction_success": request_error is None and row.get("error") is None
                                and row.get("pred_label") not in (None, "")})
                if not row["prediction_success"]:
                    failures.append(row)
                candidate_decisions.append(row)
                case_decisions.append(row)
            stream.write(json.dumps({"case_id": case["case_id"], "workflow": case["workflow"],
                "state": case["state"], "questions": case["questions"], "gold": case["gold"],
                "model": MODEL_ID, "source": "official-python-laya", "latency_ms": elapsed_ms,
                "request_error": request_error, "decisions": case_decisions},
                ensure_ascii=False, separators=(",", ":")) + "\n")
            if index % 5 == 0 or index == len(cases):
                print(f"PROGRESS cases={index}/{len(cases)}", flush=True)

    # Use the baseline's unchanged scorer/summary renderer for direct comparability.
    baseline.LAYA_DECIDE_ENDPOINT = MODEL_ID
    base_decisions: list[dict[str, Any]] = []
    base_latencies: list[float] = []
    for case in cases:
        old = baseline_by_case.get(case["case_id"])
        if old is None:
            raise RuntimeError(f"Baseline row missing for {case['case_id']}")
        base_latencies.append(float(old["latency_ms"]))
        base_decisions.extend(old["decisions"])
    candidate_summary = baseline.make_summary(cases, candidate_decisions, latencies,
        [all(d["prediction_success"] for d in candidate_decisions[i*5:(i+1)*5])
         for i in range(len(cases))], Counter({"onnx": 0, "fallback": 0, "unknown": len(cases), "no_response": 0}),
        started, {p.name: baseline.sha256(p) for p in (DATASET, BENCH / "dataset" / "test-00000-of-00001.parquet")})
    candidate_summary["model_configuration"] = MODEL_ID
    candidate_summary["endpoint"] = MODEL_ID
    candidate_summary["model_revision"] = getattr(agent, "revision", None)
    candidate_summary["runtime_version"] = __import__("importlib.metadata", fromlist=["version"]).version("laya")
    candidate_summary["device"] = "cpu"
    candidate_summary["evaluation_scope"] = "full test" if full else f"first {len(cases)} official test cases (pilot)"
    candidate_summary["source_counts"] = {"official-python-laya": len(cases)}
    candidate_summary["failed_rows"] = len(failures)
    candidate_summary["completed_at"] = datetime.now(timezone.utc).isoformat()

    baseline_summary = baseline.make_summary(cases, base_decisions, base_latencies,
        [True] * len(cases), Counter({"onnx": len(cases), "fallback": 0, "unknown": 0, "no_response": 0}),
        started, {p.name: baseline.sha256(p) for p in (DATASET, BENCH / "dataset" / "test-00000-of-00001.parquet")})
    baseline_summary["model_configuration"] = "convaiinnovations/laya via @receptron/laya 0.1.2"
    baseline_summary["evaluation_scope"] = candidate_summary["evaluation_scope"]

    summary = {"candidate": candidate_summary, "baseline_same_cases": baseline_summary}
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report_path.write_text(baseline.render_report(candidate_summary, failures) +
        "\n\n## Paired baseline scope\n\n" + json.dumps(baseline_summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidate": candidate_summary, "baseline_same_cases": baseline_summary}, indent=2), flush=True)
    close = getattr(agent, "close", None)
    if callable(close):
        close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pilot", action="store_true", help="run first 10 cases per workflow (200 decisions total)")
    group.add_argument("--full", action="store_true", help="run all 400 official test cases")
    args = parser.parse_args()
    run(args.pilot, args.full)
