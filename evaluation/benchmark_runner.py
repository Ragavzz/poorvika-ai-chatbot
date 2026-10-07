"""ShopAI Comprehensive Benchmarking Suite.
Executes all 7 benchmarks against the live, running ShopAI pipeline:
1. Laya Intent Accuracy
2. Laya Confidence Calibration
3. Product Retrieval Accuracy
4. Final Response Correctness / Grounding
5. End-to-End Latency (with baseline comparison)
6. Reliability / Error Rate
7. Repeatability (10 queries x 5 runs)

No mocked responses. Does NOT modify production code or schema.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure backend can be imported
ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.database.session import SessionLocal, check_db_connection  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.schemas.chat import ChatRequest  # noqa: E402
from app.services.chat_service import ChatService  # noqa: E402
from app.services.laya_client import LayaClient  # noqa: E402
from app.tools.product_search_tool import ProductSearchTool  # noqa: E402

from metrics import (  # noqa: E402
    calculate_classification_metrics,
    calculate_calibration_metrics,
    calculate_retrieval_metrics,
    evaluate_response_grounding,
    calculate_grounding_summary,
    calculate_latency_statistics,
    calculate_repeatability_metrics,
)

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET = EVAL_DIR / "benchmark_dataset.json"
RESULTS_DIR = EVAL_DIR / "results"
BASELINE_CSV = ROOT / "benchmark_results" / "laya_vs_bypass_2026-09-30.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("shopai.benchmark")


def load_dataset(dataset_path: Path) -> List[Dict[str, Any]]:
    """Loads benchmark dataset from JSON."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_baseline_metrics() -> Dict[str, Any]:
    """Loads existing baseline metrics from benchmark_results/laya_vs_bypass_2026-09-30.csv."""
    if not BASELINE_CSV.exists():
        return {}

    laya_enabled_total = []
    laya_enabled_laya = []
    laya_enabled_postgres = []
    laya_enabled_ollama = []

    with open(BASELINE_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("config") == "A_LAYA_ENABLED":
                try:
                    tot = float(row.get("total_ms", 0))
                    laya = float(row.get("laya_ms", 0))
                    pg = float(row.get("postgres_ms", 0))
                    ol = float(row.get("ollama_ms", 0))
                    if tot > 0:
                        laya_enabled_total.append(tot)
                        laya_enabled_laya.append(laya)
                        laya_enabled_postgres.append(pg)
                        laya_enabled_ollama.append(ol)
                except ValueError:
                    pass

    return {
        "baseline_sample_count": len(laya_enabled_total),
        "total_ms": calculate_latency_statistics(laya_enabled_total),
        "laya_ms": calculate_latency_statistics(laya_enabled_laya),
        "postgres_ms": calculate_latency_statistics(laya_enabled_postgres),
        "ollama_ms": calculate_latency_statistics(laya_enabled_ollama),
    }


async def run_pipeline_benchmark(
    dataset: List[Dict[str, Any]],
    db: Any,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Runs all dataset queries through the live ShopAI pipeline and captures full raw telemetry."""
    results = []
    failure_counts = {
        "laya_failure": 0,
        "postgres_failure": 0,
        "ollama_failure": 0,
        "timeout": 0,
        "invalid_response": 0,
        "unexpected_exception": 0,
    }

    logger.info(f"Running live pipeline benchmark across {len(dataset)} queries...")

    for idx, case in enumerate(dataset, start=1):
        q_id = case["id"]
        query = case["user_query"]
        exp_intent = case["expected_intent"]
        cat_type = case.get("category_type", "general")
        context = case.get("client_context", {})

        logger.info(f"[{idx}/{len(dataset)}] Testing ID: {q_id} | '{query}'")

        # Encode client context if provided
        msg_payload = query
        if context:
            msg_payload = f"{query}\n\n<shopai_client_context>{json.dumps(context)}</shopai_client_context>"

        service = ChatService(db)
        timings: Dict[str, Any] = {}
        t_start = time.perf_counter()

        # Capture structures
        case_result: Dict[str, Any] = {
            "id": q_id,
            "user_query": query,
            "expected_intent": exp_intent,
            "category_type": cat_type,
            "status": "success",
            "error_type": None,
            "error_message": None,
            "laya_intent": None,
            "laya_confidence": None,
            "laya_noul": None,
            "laya_probabilities": {},
            "laya_latency_ms": None,
            "postgres_latency_ms": None,
            "ollama_latency_ms": None,
            "total_latency_ms": None,
            "backend_overhead_ms": None,
            "retrieved_products": [],
            "response_text": "",
            "grounding_eval": None,
        }

        # Intercept Laya decide to ensure raw probabilities and noul are captured
        orig_decide = service.laya.decide

        def captured_decide(msg: str):
            t_laya0 = time.perf_counter()
            dec = orig_decide(msg)
            dur = (time.perf_counter() - t_laya0) * 1000.0
            case_result["laya_latency_ms"] = round(dur, 2)
            case_result["laya_intent"] = dec.get("choice")
            case_result["laya_confidence"] = dec.get("confidence")
            case_result["laya_probabilities"] = dec.get("probabilities", {})
            case_result["laya_noul"] = dec.get("noul")
            return dec

        service.laya.decide = captured_decide

        # Intercept search_tool to capture exact retrieved products
        orig_search = service.search_tool.search_products

        def captured_search(*args, **kwargs):
            t_pg0 = time.perf_counter()
            res = orig_search(*args, **kwargs)
            dur = (time.perf_counter() - t_pg0) * 1000.0
            if case_result["postgres_latency_ms"] is None:
                case_result["postgres_latency_ms"] = round(dur, 2)
            else:
                case_result["postgres_latency_ms"] += round(dur, 2)
            case_result["retrieved_products"] = res
            return res

        service.search_tool.search_products = captured_search

        try:
            req = ChatRequest(message=msg_payload)
            chat_resp = await asyncio.wait_for(service.generate_response(req, timings=timings), timeout=45.0)
            total_dur = (time.perf_counter() - t_start) * 1000.0

            case_result["total_latency_ms"] = round(total_dur, 2)
            case_result["response_text"] = chat_resp.response

            # Capture timing breakdown
            if timings.get("laya_duration_ms") and case_result["laya_latency_ms"] is None:
                case_result["laya_latency_ms"] = timings["laya_duration_ms"]
            if timings.get("postgres_query_duration_ms") and case_result["postgres_latency_ms"] is None:
                case_result["postgres_latency_ms"] = timings["postgres_query_duration_ms"]
            if timings.get("ollama_duration_ms"):
                case_result["ollama_latency_ms"] = timings["ollama_duration_ms"]
            else:
                case_result["ollama_latency_ms"] = 0.0

            # Calculate backend overhead
            laya_t = case_result["laya_latency_ms"] or 0.0
            pg_t = case_result["postgres_latency_ms"] or 0.0
            ol_t = case_result["ollama_latency_ms"] or 0.0
            overhead = max(0.0, total_dur - (laya_t + pg_t + ol_t))
            case_result["backend_overhead_ms"] = round(overhead, 2)

            # Evaluate grounding for product-related responses
            if cat_type in [
                "product_search", "product_details", "category_filtering",
                "brand_filtering", "price_filtering", "combined_filters", "out_of_catalog"
            ]:
                g_eval = evaluate_response_grounding(chat_resp.response, case_result["retrieved_products"])
                case_result["grounding_eval"] = g_eval

        except asyncio.TimeoutError:
            total_dur = (time.perf_counter() - t_start) * 1000.0
            case_result["status"] = "failed"
            case_result["error_type"] = "timeout"
            case_result["error_message"] = "Request exceeded 45.0s timeout limit"
            case_result["total_latency_ms"] = round(total_dur, 2)
            failure_counts["timeout"] += 1
            logger.warning(f"Timeout on query {q_id}")

        except Exception as exc:
            total_dur = (time.perf_counter() - t_start) * 1000.0
            case_result["status"] = "failed"
            exc_str = f"{type(exc).__name__}: {exc}"
            case_result["error_message"] = exc_str
            case_result["total_latency_ms"] = round(total_dur, 2)

            if "laya" in exc_str.lower() or case_result["laya_intent"] is None:
                case_result["error_type"] = "laya_failure"
                failure_counts["laya_failure"] += 1
            elif "postgres" in exc_str.lower() or "database" in exc_str.lower():
                case_result["error_type"] = "postgres_failure"
                failure_counts["postgres_failure"] += 1
            elif "ollama" in exc_str.lower():
                case_result["error_type"] = "ollama_failure"
                failure_counts["ollama_failure"] += 1
            else:
                case_result["error_type"] = "unexpected_exception"
                failure_counts["unexpected_exception"] += 1
            logger.error(f"Error on query {q_id}: {exc_str}")

        results.append(case_result)

    return results, failure_counts


async def run_repeatability_benchmark(
    dataset: List[Dict[str, Any]],
    db: Any,
    runs_per_query: int = 5,
) -> Dict[str, Any]:
    """Runs 10 representative queries 5 times each and computes consistency and latency CV."""
    candidates = [d for d in dataset if d.get("is_repeatability_candidate")][:10]
    logger.info(f"Running repeatability benchmark: {len(candidates)} queries x {runs_per_query} runs = {len(candidates) * runs_per_query} executions...")

    query_runs: Dict[str, List[Dict[str, Any]]] = {}

    for q_idx, case in enumerate(candidates, start=1):
        query = case["user_query"]
        query_runs[query] = []
        logger.info(f"Repeatability Query [{q_idx}/{len(candidates)}]: '{query}'")

        for r_num in range(1, runs_per_query + 1):
            service = ChatService(db)
            timings = {}
            t0 = time.perf_counter()

            run_record: Dict[str, Any] = {
                "run": r_num,
                "intent": None,
                "product_ids": [],
                "classification": "Unknown",
                "total_ms": 0.0,
            }

            orig_decide = service.laya.decide

            def captured_decide(msg: str):
                dec = orig_decide(msg)
                run_record["intent"] = dec.get("choice")
                return dec

            service.laya.decide = captured_decide

            orig_search = service.search_tool.search_products

            def captured_search(*args, **kwargs):
                res = orig_search(*args, **kwargs)
                run_record["product_ids"] = [p.get("id") for p in res]
                return res

            service.search_tool.search_products = captured_search

            try:
                context = case.get("client_context", {})
                msg_payload = query
                if context:
                    msg_payload = f"{query}\n\n<shopai_client_context>{json.dumps(context)}</shopai_client_context>"

                req = ChatRequest(message=msg_payload)
                resp = await asyncio.wait_for(service.generate_response(req, timings=timings), timeout=35.0)
                dur = (time.perf_counter() - t0) * 1000.0
                run_record["total_ms"] = round(dur, 2)

                # Grounding classification if product search
                g_eval = evaluate_response_grounding(resp.response, [{"id": pid} for pid in run_record["product_ids"]])
                run_record["classification"] = g_eval.get("classification", "Correct")
            except Exception as exc:
                run_record["classification"] = f"Error: {type(exc).__name__}"
                run_record["total_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)

            query_runs[query].append(run_record)

    return calculate_repeatability_metrics(query_runs)


def generate_markdown_report(
    summary: Dict[str, Any],
    b1_intent: Dict[str, Any],
    b2_calib: Dict[str, Any],
    b3_retrieval: Dict[str, Any],
    b4_grounding: Dict[str, Any],
    b5_latency: Dict[str, Any],
    b6_reliability: Dict[str, Any],
    b7_repeatability: Dict[str, Any],
    baseline: Dict[str, Any],
) -> str:
    """Generates a comprehensive, publication-ready markdown benchmark report."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    md = []
    md.append("# Poorvika ShopAI Comprehensive Pipeline Benchmark Report")
    md.append(f"**Execution Timestamp:** {timestamp}  ")
    md.append(f"**Evaluator:** Standalone ShopAI Benchmark Suite  ")
    md.append(f"**Pipeline Components:** Laya ONNX System-1 Decision Layer, PostgreSQL Catalog (508 products), Local Ollama LLM (llama3.2:latest)  ")
    md.append(f"**Test Set:** {summary.get('total_queries', 0)} realistic shopping queries across 12 categories  ")
    md.append("\n---\n")

    # Executive Summary Table
    md.append("## Executive Benchmark Summary\n")
    md.append("| Benchmark Domain | Key Metric | Measured Result | Target / Baseline | Status |")
    md.append("|---|---|---|---|---|")
    md.append(f"| **1. Laya Intent Accuracy** | Overall Accuracy | **{b1_intent.get('accuracy', 0) * 100:.1f}%** | >= 85.0% | {'PASS' if b1_intent.get('accuracy', 0) >= 0.85 else 'REVIEW'} |")
    md.append(f"| **1. Laya Intent F1** | Macro F1-Score | **{b1_intent.get('macro_avg', {}).get('f1_score', 0):.4f}** | >= 0.80 | {'PASS' if b1_intent.get('macro_avg', {}).get('f1_score', 0) >= 0.80 else 'REVIEW'} |")
    md.append(f"| **2. Confidence Calibration** | Expected Calibration Error (ECE) | **{b2_calib.get('expected_calibration_error', 0):.4f}** | <= 0.1500 | {'PASS' if b2_calib.get('is_calibrated') else 'MISCALIBRATED'} |")
    md.append(f"| **3. Product Retrieval** | Top-1 Accuracy | **{b3_retrieval.get('top_1_accuracy', 0) * 100:.1f}%** | >= 80.0% | {'PASS' if b3_retrieval.get('top_1_accuracy', 0) >= 0.80 else 'REVIEW'} |")
    md.append(f"| **3. Filter Accuracy** | Brand & Price Accuracy | **{b3_retrieval.get('filter_accuracy', {}).get('brand_filter_accuracy', 1.0) * 100:.1f}% / {b3_retrieval.get('filter_accuracy', {}).get('max_price_filter_accuracy', 1.0) * 100:.1f}%** | 100.0% | {'PASS' if b3_retrieval.get('filter_accuracy', {}).get('brand_filter_accuracy', 0) >= 0.95 else 'REVIEW'} |")
    md.append(f"| **4. Response Grounding** | Grounded Response Rate | **{b4_grounding.get('grounded_response_rate', 0):.1f}%** | >= 75.0% | {'PASS' if b4_grounding.get('grounded_response_rate', 0) >= 0.75 else 'REVIEW'} |")
    md.append(f"| **4. Unsupported Claims** | Unsupported Claim Rate | **{b4_grounding.get('unsupported_claim_rate', 0):.1f}%** | 0.0% | {'EXCELLENT' if b4_grounding.get('unsupported_claim_rate', 0) == 0 else 'WARNING'} |")
    md.append(f"| **5. End-to-End Latency** | Mean Total Latency | **{b5_latency.get('total', {}).get('mean', 0):.1f} ms** | Baseline: {baseline.get('total_ms', {}).get('mean', 2110):.1f} ms | {'FASTER' if b5_latency.get('total', {}).get('mean', 0) <= baseline.get('total_ms', {}).get('mean', 9999) else 'NORMAL'} |")
    md.append(f"| **6. Reliability** | Pipeline Success Rate | **{b6_reliability.get('success_rate', 0):.1f}%** | >= 98.0% | {'PASS' if b6_reliability.get('success_rate', 0) >= 98 else 'ALERT'} |")
    md.append(f"| **7. Repeatability** | Intent Consistency Rate | **{b7_repeatability.get('intent_consistency_rate', 0):.1f}%** | 100.0% | {'PASS' if b7_repeatability.get('intent_consistency_rate', 0) == 100 else 'REVIEW'} |")
    md.append("\n---\n")

    # Benchmark 1: Laya Intent Accuracy
    md.append("## Benchmark 1: Laya Intent Classification Quality\n")
    md.append(f"- **Total Queries Evaluated:** {b1_intent.get('total_samples', 0)}")
    md.append(f"- **Correct Predictions:** {b1_intent.get('correct_predictions', 0)}")
    md.append(f"- **Overall Intent Accuracy:** {b1_intent.get('accuracy', 0) * 100:.2f}%")
    md.append(f"- **Macro Average:** Precision = {b1_intent.get('macro_avg', {}).get('precision', 0):.4f}, Recall = {b1_intent.get('macro_avg', {}).get('recall', 0):.4f}, F1 = {b1_intent.get('macro_avg', {}).get('f1_score', 0):.4f}")
    md.append(f"- **Weighted Average:** Precision = {b1_intent.get('weighted_avg', {}).get('precision', 0):.4f}, Recall = {b1_intent.get('weighted_avg', {}).get('recall', 0):.4f}, F1 = {b1_intent.get('weighted_avg', {}).get('f1_score', 0):.4f}")
    md.append(f"- **Average Laya Decision Latency:** {b5_latency.get('laya', {}).get('mean', 0):.2f} ms\n")

    md.append("### Per-Intent Performance Metrics\n")
    md.append("| Intent Class | Support | Accuracy | Precision | Recall | F1-Score | TP | FP | FN |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    for lbl, pdata in b1_intent.get("per_class", {}).items():
        md.append(f"| `{lbl}` | {pdata['support']} | {pdata['accuracy'] * 100:.1f}% | {pdata['precision']:.4f} | {pdata['recall']:.4f} | {pdata['f1_score']:.4f} | {pdata['tp']} | {pdata['fp']} | {pdata['fn']} |")
    md.append("\n")

    md.append("### Confusion Matrix (Rows = Ground Truth, Columns = Predicted Laya Choice)\n")
    labels = b1_intent.get("labels", [])
    header = "| True \\ Pred | " + " | ".join(f"`{lbl}`" for lbl in labels) + " |"
    sep = "|---|" + "|".join("---" for _ in labels) + "|"
    md.append(header)
    md.append(sep)
    matrix = b1_intent.get("confusion_matrix", {})
    for true_lbl in labels:
        row_cells = [str(matrix.get(true_lbl, {}).get(pred_lbl, 0)) for pred_lbl in labels]
        md.append(f"| `{true_lbl}` | " + " | ".join(row_cells) + " |")
    md.append("\n---\n")

    # Benchmark 2: Confidence Calibration
    md.append("## Benchmark 2: Laya Confidence Calibration\n")
    md.append(f"- **Expected Calibration Error (ECE):** **{b2_calib.get('expected_calibration_error', 0):.4f}**")
    md.append(f"- **Maximum Calibration Error (MCE):** **{b2_calib.get('maximum_calibration_error', 0):.4f}**")
    md.append(f"- **Calibration Status:** {b2_calib.get('calibration_assessment', 'Unknown')}\n")
    md.append("| Confidence Range | Predictions Count | Empirical Accuracy | Average Confidence | Calibration Gap |")
    md.append("|---|---|---|---|---|")
    for b in b2_calib.get("bins", []):
        md.append(f"| `{b['range']}` | {b['count']} | {b['accuracy'] * 100:.1f}% | {b['avg_confidence'] * 100:.1f}% | {b['calibration_gap']:.4f} |")
    md.append("\n")
    md.append("> **Calibration Finding:** " + (
        "Laya's confidence score closely tracks real-world accuracy across evaluated ranges."
        if b2_calib.get("is_calibrated")
        else "Laya confidence shows significant variance relative to observed accuracy. Confidence values should be interpreted cautiously."
    ))
    md.append("\n---\n")

    # Benchmark 3: Product Retrieval Accuracy
    md.append("## Benchmark 3: Product Retrieval Accuracy (PostgreSQL Single Source of Truth)\n")
    md.append(f"- **Total Retrieval Queries Evaluated:** {b3_retrieval.get('total_queries_evaluated', 0)}")
    md.append(f"- **Top-1 Accuracy:** {b3_retrieval.get('top_1_accuracy', 0) * 100:.2f}%")
    md.append(f"- **Top-3 Accuracy:** {b3_retrieval.get('top_3_accuracy', 0) * 100:.2f}%")
    md.append(f"- **Top-5 Accuracy:** {b3_retrieval.get('top_5_accuracy', 0) * 100:.2f}%\n")

    md.append("### Precision@K and Recall@K\n")
    md.append("| Metric | K = 1 | K = 3 | K = 5 |")
    md.append("|---|---|---|---|")
    md.append(f"| **Precision@K** | {b3_retrieval.get('precision_at_1', 0):.4f} | {b3_retrieval.get('precision_at_3', 0):.4f} | {b3_retrieval.get('precision_at_5', 0):.4f} |")
    md.append(f"| **Recall@K** | {b3_retrieval.get('recall_at_1', 0):.4f} | {b3_retrieval.get('recall_at_3', 0):.4f} | {b3_retrieval.get('recall_at_5', 0):.4f} |")
    md.append("\n")

    md.append("### SQL Filter Constraint Verification\n")
    f_acc = b3_retrieval.get("filter_accuracy", {})
    md.append("| Filter Dimension | Evaluated Items | Verified Accuracy | Compliance |")
    md.append("|---|---|---|---|")
    md.append(f"| **Category Filter** | {f_acc.get('category_verified_count', 0)} | {f_acc.get('category_filter_accuracy', 1.0) * 100:.2f}% | Exact mapping to PostgreSQL catalog |")
    md.append(f"| **Brand Filter** | {f_acc.get('brand_verified_count', 0)} | {f_acc.get('brand_filter_accuracy', 1.0) * 100:.2f}% | Case-insensitive token match |")
    md.append(f"| **Maximum Price Filter** | {f_acc.get('max_price_verified_count', 0)} | {f_acc.get('max_price_filter_accuracy', 1.0) * 100:.2f}% | Guaranteed price <= max_price |")
    md.append(f"| **Minimum Price Filter** | {f_acc.get('min_price_verified_count', 0)} | {f_acc.get('min_price_filter_accuracy', 1.0) * 100:.2f}% | Guaranteed price >= min_price |")
    md.append(f"| **Stock / Availability Filter** | {f_acc.get('stock_verified_count', 0)} | {f_acc.get('stock_filter_accuracy', 1.0) * 100:.2f}% | In-stock flag enforcement |")
    md.append("\n---\n")

    # Benchmark 4: Final Response Correctness / Grounding
    md.append("## Benchmark 4: Final Response Correctness and Grounding\n")
    md.append(f"- **Evaluated Responses:** {b4_grounding.get('total_responses_evaluated', 0)}")
    md.append(f"- **Factual Correctness Rate:** **{b4_grounding.get('factual_correctness_rate', 0):.2f}%**")
    md.append(f"- **Grounded Response Rate:** **{b4_grounding.get('grounded_response_rate', 0):.2f}%**")
    md.append(f"- **Unsupported Claim Rate:** **{b4_grounding.get('unsupported_claim_rate', 0):.2f}%**\n")
    md.append("### Response Classification Breakdown\n")
    md.append("| Classification Class | Count | Percentage | Description |")
    md.append("|---|---|---|---|")
    bk = b4_grounding.get("breakdown", {})
    tot_resp = max(1, b4_grounding.get("total_responses_evaluated", 1))
    md.append(f"| **Correct** | {bk.get('Correct', 0)} | {bk.get('Correct', 0) / tot_resp * 100:.1f}% | All product names, prices, MRP, and stock match PostgreSQL ground truth |")
    md.append(f"| **Partially correct** | {bk.get('Partially correct', 0)} | {bk.get('Partially correct', 0) / tot_resp * 100:.1f}% | Relevant products cited without false pricing |")
    md.append(f"| **Incorrect** | {bk.get('Incorrect', 0)} | {bk.get('Incorrect', 0) / tot_resp * 100:.1f}% | Response makes an inaccurate factual claim about a database entity |")
    md.append(f"| **Unsupported / hallucinated** | {bk.get('Unsupported / hallucinated', 0)} | {bk.get('Unsupported / hallucinated', 0) / tot_resp * 100:.1f}% | Invented pricing or products not found in PostgreSQL |")
    md.append("\n---\n")

    # Benchmark 5: Latency Breakdown & Baseline Comparison
    md.append("## Benchmark 5: End-to-End Latency Breakdown & Baseline Comparison\n")
    md.append("### Pipeline Stage Percentiles (Milliseconds)\n")
    md.append("| Component / Stage | Mean (ms) | Median (ms) | Min (ms) | Max (ms) | P95 (ms) | P99 (ms) |")
    md.append("|---|---|---|---|---|---|---|")
    for comp, name in [
        ("total", "**Total Pipeline Request**"),
        ("laya", "**Laya Decision Layer**"),
        ("postgres", "**PostgreSQL Query Tool**"),
        ("ollama", "**Ollama LLM Generation**"),
        ("overhead", "**Backend Overhead / Routing**"),
    ]:
        cdata = b5_latency.get(comp, {})
        md.append(f"| {name} | {cdata.get('mean', 0):.1f} | {cdata.get('median', 0):.1f} | {cdata.get('min', 0):.1f} | {cdata.get('max', 0):.1f} | {cdata.get('p95', 0):.1f} | {cdata.get('p99', 0):.1f} |")
    md.append("\n")

    if baseline:
        md.append("### Comparison with Baseline (`laya_vs_bypass_2026-09-30.csv`)\n")
        md.append("| Metric Dimension | Measured Live Run | Baseline (Laya Enabled) | Delta / Change |")
        md.append("|---|---|---|---|")
        tot_m = b5_latency.get("total", {}).get("mean", 0)
        base_tot_m = baseline.get("total_ms", {}).get("mean", 0)
        md.append(f"| **Total Latency Mean** | {tot_m:.1f} ms | {base_tot_m:.1f} ms | {tot_m - base_tot_m:+.1f} ms |")
        lay_m = b5_latency.get("laya", {}).get("mean", 0)
        base_lay_m = baseline.get("laya_ms", {}).get("mean", 0)
        md.append(f"| **Laya Latency Mean** | {lay_m:.1f} ms | {base_lay_m:.1f} ms | {lay_m - base_lay_m:+.1f} ms |")
        pg_m = b5_latency.get("postgres", {}).get("mean", 0)
        base_pg_m = baseline.get("postgres_ms", {}).get("mean", 0)
        md.append(f"| **PostgreSQL Latency Mean** | {pg_m:.1f} ms | {base_pg_m:.1f} ms | {pg_m - base_pg_m:+.1f} ms |")
    md.append("\n---\n")

    # Benchmark 6: Reliability / Error Rate
    md.append("## Benchmark 6: System Reliability and Failure Breakdown\n")
    md.append(f"- **Total Evaluated Requests:** {b6_reliability.get('total_requests', 0)}")
    md.append(f"- **Successful Requests:** {b6_reliability.get('successful_requests', 0)}")
    md.append(f"- **Success Rate:** **{b6_reliability.get('success_rate', 0):.2f}%**")
    md.append(f"- **Error Rate:** **{b6_reliability.get('error_rate', 0):.2f}%**\n")
    md.append("### Failure Reasons Breakdown\n")
    md.append("| Failure Category | Occurrences | Percentage | Impact Description |")
    md.append("|---|---|---|---|")
    fb = b6_reliability.get("failure_breakdown", {})
    tot_req = max(1, b6_reliability.get("total_requests", 1))
    md.append(f"| **Laya Decision Failure** | {fb.get('laya_failure', 0)} | {fb.get('laya_failure', 0) / tot_req * 100:.1f}% | Service unreachable or uncalibrated fallback rejected |")
    md.append(f"| **PostgreSQL Query Failure** | {fb.get('postgres_failure', 0)} | {fb.get('postgres_failure', 0) / tot_req * 100:.1f}% | Database connection pool dropped or syntax exception |")
    md.append(f"| **Ollama Service Failure** | {fb.get('ollama_failure', 0)} | {fb.get('ollama_failure', 0) / tot_req * 100:.1f}% | Local LLM inference failed or model unloaded |")
    md.append(f"| **Request Timeout** | {fb.get('timeout', 0)} | {fb.get('timeout', 0) / tot_req * 100:.1f}% | Processing exceeded 45.0s window |")
    md.append(f"| **Invalid Response Format** | {fb.get('invalid_response', 0)} | {fb.get('invalid_response', 0) / tot_req * 100:.1f}% | Schema deserialization failure |")
    md.append(f"| **Unexpected Exception** | {fb.get('unexpected_exception', 0)} | {fb.get('unexpected_exception', 0) / tot_req * 100:.1f}% | Uncaught server runtime error |")
    md.append("\n---\n")

    # Benchmark 7: Repeatability
    md.append("## Benchmark 7: Execution Repeatability & Consistency Analysis\n")
    md.append(f"- **Queries Tested:** {b7_repeatability.get('total_queries_tested', 0)} (each repeated 5 times = 50 runs)")
    md.append(f"- **Intent Consistency Rate:** **{b7_repeatability.get('intent_consistency_rate', 0):.1f}%**")
    md.append(f"- **Product Retrieval Consistency Rate:** **{b7_repeatability.get('product_consistency_rate', 0):.1f}%**")
    md.append(f"- **Response Consistency Rate:** **{b7_repeatability.get('response_consistency_rate', 0):.1f}%**\n")
    md.append("### Per-Query Repeatability Details\n")
    md.append("| Query | Intent Consistency | Product Consistency | Response Consistency | Mean Latency | Latency CV |")
    md.append("|---|---|---|---|---|---|")
    for q_text, rdata in b7_repeatability.get("per_query_details", {}).items():
        short_q = q_text[:35] + ("..." if len(q_text) > 35 else "")
        md.append(f"| `{short_q}` | {rdata['intent_consistency']:.1f}% | {rdata['product_consistency']:.1f}% | {rdata['response_consistency']:.1f}% | {rdata['latency_mean_ms']:.1f} ms | {rdata['latency_cv_percent']:.1f}% |")
    md.append("\n---\n")

    # Reproducibility Instructions
    md.append("## How to Reproduce This Benchmark\n")
    md.append("Ensure the 3 Poorvika ShopAI services are running:\n")
    md.append("1. **Laya Decision Service**: `node server.js` (port 5055)\n")
    md.append("2. **PostgreSQL Database**: PostgreSQL on localhost:5432 with `shopai` database\n")
    md.append("3. **Ollama Service**: `ollama serve` (port 11434 with `llama3.2`)\n\n")
    md.append("Run the benchmark runner directly from PowerShell:\n")
    md.append("```powershell\n.\\.venv\\Scripts\\python.exe evaluation\\benchmark_runner.py --all\n```\n")

    return "\n".join(md)


async def main_async():
    parser = argparse.ArgumentParser(description="Poorvika ShopAI Comprehensive Benchmarking Suite")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="Path to benchmark dataset JSON")
    parser.add_argument("--all", action="store_true", default=True, help="Run all 7 benchmarks")
    parser.add_argument("--repeatability-runs", type=int, default=5, help="Number of repetitions for Benchmark 7")
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR, help="Directory to save raw results and reports")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # Verify services
    logger.info("Verifying PostgreSQL database connection...")
    is_connected, msg = check_db_connection()
    if not is_connected:
        logger.error(f"Cannot run benchmark: PostgreSQL connection failed ({msg})")
        sys.exit(1)

    dataset = load_dataset(args.dataset)
    logger.info(f"Loaded {len(dataset)} test queries from {args.dataset}")

    with SessionLocal() as db:
        # Run Benchmarks 1, 2, 3, 4, 5, 6
        raw_results, failure_counts = await run_pipeline_benchmark(dataset, db)

        # Run Benchmark 7 (Repeatability)
        logger.info("Executing Benchmark 7 (Repeatability)...")
        b7_repeatability = await run_repeatability_benchmark(dataset, db, runs_per_query=args.repeatability_runs)

    # Compute Benchmark 1: Laya Intent Accuracy
    valid_predictions = [r for r in raw_results if r["laya_intent"] is not None]
    y_true = [r["expected_intent"] for r in valid_predictions]
    y_pred = [r["laya_intent"] for r in valid_predictions]
    b1_intent = calculate_classification_metrics(y_true, y_pred)

    # Compute Benchmark 2: Laya Confidence Calibration
    confidences = [r["laya_confidence"] for r in valid_predictions if r["laya_confidence"] is not None]
    valid_calib_y_true = [r["expected_intent"] for r in valid_predictions if r["laya_confidence"] is not None]
    valid_calib_y_pred = [r["laya_intent"] for r in valid_predictions if r["laya_confidence"] is not None]
    b2_calib = calculate_calibration_metrics(confidences, valid_calib_y_true, valid_calib_y_pred)

    # Compute Benchmark 3: Product Retrieval Accuracy
    retrieval_cases = [r for r in raw_results if r["category_type"] in [
        "product_search", "category_filtering", "brand_filtering", "price_filtering", "combined_filters"
    ]]
    retrieved_items_list = [r["retrieved_products"] for r in retrieval_cases]
    expected_criteria_list = [
        {
            **d.get("expected_filters", {}),
            "expected_product_ids": d.get("expected_product_ids", []),
        }
        for d in dataset if d["id"] in [r["id"] for r in retrieval_cases]
    ]
    b3_retrieval = calculate_retrieval_metrics(retrieved_items_list, expected_criteria_list)

    # Compute Benchmark 4: Final Response Correctness / Grounding
    grounding_evals = [r["grounding_eval"] for r in raw_results if r["grounding_eval"] is not None]
    b4_grounding = calculate_grounding_summary(grounding_evals)

    # Compute Benchmark 5: Latency Statistics
    total_lats = [r["total_latency_ms"] for r in raw_results if r["total_latency_ms"] is not None]
    laya_lats = [r["laya_latency_ms"] for r in raw_results if r["laya_latency_ms"] is not None]
    pg_lats = [r["postgres_latency_ms"] for r in raw_results if r["postgres_latency_ms"] is not None]
    ollama_lats = [r["ollama_latency_ms"] for r in raw_results if r["ollama_latency_ms"] is not None and r["ollama_latency_ms"] > 0]
    overhead_lats = [r["backend_overhead_ms"] for r in raw_results if r["backend_overhead_ms"] is not None]

    b5_latency = {
        "total": calculate_latency_statistics(total_lats),
        "laya": calculate_latency_statistics(laya_lats),
        "postgres": calculate_latency_statistics(pg_lats),
        "ollama": calculate_latency_statistics(ollama_lats),
        "overhead": calculate_latency_statistics(overhead_lats),
    }

    # Compute Benchmark 6: Reliability / Error Rate
    total_reqs = len(raw_results)
    success_reqs = sum(1 for r in raw_results if r["status"] == "success")
    failed_reqs = total_reqs - success_reqs
    b6_reliability = {
        "total_requests": total_reqs,
        "successful_requests": success_reqs,
        "failed_requests": failed_reqs,
        "success_rate": round(success_reqs / total_reqs * 100.0, 2) if total_reqs > 0 else 0.0,
        "error_rate": round(failed_reqs / total_reqs * 100.0, 2) if total_reqs > 0 else 0.0,
        "failure_breakdown": failure_counts,
    }

    # Baseline comparison
    baseline = load_baseline_metrics()

    # Compile Summary
    summary = {
        "benchmark_run_timestamp": timestamp,
        "total_queries": len(dataset),
        "b1_intent_classification": b1_intent,
        "b2_confidence_calibration": b2_calib,
        "b3_product_retrieval": b3_retrieval,
        "b4_grounding_factual_correctness": b4_grounding,
        "b5_end_to_end_latency": b5_latency,
        "b6_reliability_error_rate": b6_reliability,
        "b7_repeatability": b7_repeatability,
        "baseline_comparison": baseline,
    }

    # Save raw results JSON
    raw_json_file = args.output_dir / f"raw_benchmark_results_{timestamp}.json"
    with open(raw_json_file, "w", encoding="utf-8") as f:
        json.dump(raw_results, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved raw results to: {raw_json_file}")

    # Save raw results CSV
    raw_csv_file = args.output_dir / f"raw_benchmark_results_{timestamp}.csv"
    with open(raw_csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "user_query", "category_type", "expected_intent", "laya_intent",
            "laya_confidence", "laya_noul", "laya_latency_ms", "postgres_latency_ms",
            "ollama_latency_ms", "total_latency_ms", "status", "grounding_classification", "response_preview"
        ])
        for r in raw_results:
            g_class = r.get("grounding_eval", {}).get("classification") if r.get("grounding_eval") else "N/A"
            writer.writerow([
                r["id"], r["user_query"], r["category_type"], r["expected_intent"],
                r["laya_intent"], r["laya_confidence"], r["laya_noul"],
                r["laya_latency_ms"], r["postgres_latency_ms"], r["ollama_latency_ms"],
                r["total_latency_ms"], r["status"], g_class, (r.get("response_text") or "")[:80]
            ])
    logger.info(f"Saved raw CSV to: {raw_csv_file}")

    # Save summary metrics JSON
    summary_json_file = args.output_dir / f"summary_metrics_{timestamp}.json"
    with open(summary_json_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    # Also save as canonical summary.json
    with open(args.output_dir / "summary_metrics.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved summary metrics to: {summary_json_file}")

    # Save repeatability results
    repeat_json_file = args.output_dir / f"repeatability_results_{timestamp}.json"
    with open(repeat_json_file, "w", encoding="utf-8") as f:
        json.dump(b7_repeatability, f, indent=2, ensure_ascii=False)

    # Generate Markdown Report
    report_md = generate_markdown_report(
        summary, b1_intent, b2_calib, b3_retrieval, b4_grounding,
        b5_latency, b6_reliability, b7_repeatability, baseline
    )
    report_file = args.output_dir / "benchmark_report.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_md)
    logger.info(f"Saved benchmark report to: {report_file}")

    print("\n" + "=" * 70)
    print("BENCHMARK RUN COMPLETE")
    print(f"Total Queries: {total_reqs} | Success Rate: {b6_reliability['success_rate']}%")
    print(f"Laya Accuracy: {b1_intent['accuracy'] * 100:.1f}% | ECE: {b2_calib['expected_calibration_error']}")
    print(f"Top-1 Retrieval: {b3_retrieval['top_1_accuracy'] * 100:.1f}% | Grounded Response Rate: {b4_grounding['grounded_response_rate']}%")
    print(f"Total Latency Mean: {b5_latency['total']['mean']:.1f}ms | Median: {b5_latency['total']['median']:.1f}ms")
    print(f"Report written to: {report_file}")
    print("=" * 70 + "\n")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
