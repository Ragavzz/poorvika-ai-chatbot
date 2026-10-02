"""Run ShopAI's real chat pipeline and score the captured results with Ragas.

Run from the repository root with the backend and Laya services available.
No code in this module is imported by the production FastAPI application.
"""

from __future__ import annotations

import asyncio
import argparse
import csv
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.database.session import SessionLocal  # noqa: E402
from app.schemas.chat import ChatRequest  # noqa: E402
from app.services.chat_service import ChatService  # noqa: E402

EVALUATION_DIR = Path(__file__).resolve().parent
DATASET_PATH = EVALUATION_DIR / "dataset.json"
RESULTS_DIR = EVALUATION_DIR / "results"
RESULTS_JSON = RESULTS_DIR / "ragas_results.json"
CAPTURE_JSON = RESULTS_DIR / "chat_responses.json"
RESULTS_CSV = RESULTS_DIR / "ragas_results.csv"
SUMMARY_JSON = RESULTS_DIR / "summary.json"


async def capture_case(db: Any, case: dict[str, str]) -> dict[str, Any]:
    """Run the unchanged chat orchestrator while observing its real service calls."""
    service = ChatService(db)
    capture: dict[str, Any] = {
        "laya_intent": None,
        "laya_confidence": None,
        "extracted_filters": None,
        "retrieved_contexts": [],
        "reference_contexts": [],
        "response_source": None,
        "search_calls": [],
        "diagnostic_searches": [],
        "actual_ollama_called": False,
        "ollama_failure": None,
        "ollama_response": None,
        "final_response_received": False,
        "evaluator_error": None,
        "error": None,
    }

    original_decide = service.laya.decide

    def capture_decision(message: str) -> dict[str, Any]:
        try:
            decision = original_decide(message)
        except Exception as exc:
            capture["error"] = f"Laya decision failed: {type(exc).__name__}: {exc}"
            raise
        capture["laya_intent"] = decision.get("choice")
        capture["laya_confidence"] = decision.get("confidence")
        return decision

    service.laya.decide = capture_decision

    original_search = service.search_tool.search_products

    def capture_search(**kwargs: Any) -> list[dict[str, Any]]:
        actual_kwargs = dict(kwargs)
        # Avoid retaining references to mutable timings inside logged filter args
        logged_filters = {k: v for k, v in actual_kwargs.items() if k != "timings"}
        if capture["extracted_filters"] is None:
            capture["extracted_filters"] = logged_filters
        try:
            results = original_search(**actual_kwargs)
        except Exception as exc:
            capture["error"] = f"PostgreSQL search failed: {type(exc).__name__}: {exc}"
            capture["search_calls"].append({
                "filters": logged_filters,
                "result_count": None,
                "error": f"{type(exc).__name__}: {exc}",
            })
            raise
        capture["search_calls"].append({
            "filters": logged_filters,
            "result_count": len(results),
            "error": None,
        })
        if results:
            rendered = json.dumps(service.ollama.product_context(results), ensure_ascii=False, sort_keys=True)
            if rendered not in capture["retrieved_contexts"]:
                capture["retrieved_contexts"].append(rendered)
            # Use the same real DB filters without the production top-five limit to
            # form a catalog-backed reference for context recall. The pipeline result
            # itself remains untouched and is still exactly what ChatService uses.
            reference_kwargs = {**actual_kwargs, "limit": 100}
            try:
                reference_products = original_search(**reference_kwargs)
            except Exception as exc:
                capture["reference_error"] = f"{type(exc).__name__}: {exc}"
                reference_products = []
            if reference_products:
                capture["reference_contexts"].append(
                    json.dumps(service.ollama.product_context(reference_products), ensure_ascii=False, sort_keys=True)
                )
        return results

    service.search_tool.search_products = capture_search

    original_get_product = service.search_tool.get_product_by_id

    def capture_get_product(product_id: str) -> dict[str, Any] | None:
        try:
            product = original_get_product(product_id)
        except Exception as exc:
            capture["retrieval_error"] = f"{type(exc).__name__}: {exc}"
            raise
        capture["selected_product_found"] = product is not None
        if product:
            rendered = json.dumps(service.ollama.product_context([product]), ensure_ascii=False, sort_keys=True)
            if rendered not in capture["retrieved_contexts"]:
                capture["retrieved_contexts"].append(rendered)
            if rendered not in capture["reference_contexts"]:
                capture["reference_contexts"].append(rendered)
        return product

    service.search_tool.get_product_by_id = capture_get_product

    original_generate = service.ollama.generate

    def capture_generate(
        message: str,
        context: dict[str, Any],
        timings: dict[str, Any] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        capture["actual_ollama_called"] = True
        try:
            products = context.get("products")
            if products:
                rendered = json.dumps(service.ollama.product_context(products), ensure_ascii=False, sort_keys=True)
                if rendered not in capture["retrieved_contexts"]:
                    capture["retrieved_contexts"].append(rendered)
        except Exception as exc:
            capture["evaluator_error"] = f"Evaluator context extraction failed: {type(exc).__name__}: {exc}"

        try:
            response = original_generate(message, context, timings=timings, *args, **kwargs)
        except Exception as exc:
            capture["ollama_failure"] = f"{type(exc).__name__}: {exc}"
            capture["response_source"] = "fallback_after_ollama_error"
            raise
        capture["response_source"] = "ollama"
        capture["ollama_response"] = response
        return response

    service.ollama.generate = capture_generate

    timings: dict[str, Any] = {}
    pipeline_failed = False
    try:
        chat_response = await service.generate_response(ChatRequest(message=case["user_input"]), timings=timings)
        response_text = chat_response.response
        capture["final_response_received"] = bool(response_text)
    except Exception as exc:
        pipeline_failed = True
        response_text = None
        capture["final_response_received"] = False
        if capture["error"] is None:
            capture["error"] = f"ChatService raised before returning a response: {type(exc).__name__}: {exc}"

    # Determine intent / action taken by ChatService
    action = capture["laya_intent"]
    if service._response_source == "deterministic_catalog" and action == "cart_action":
        action = "product_search (recovered from cart_action)"
    elif service._response_source == "deterministic_catalog" and action is None:
        action = "product_search"

    if capture["extracted_filters"] is None:
        try:
            capture["extracted_filters"] = service._filters(case["user_input"])
        except Exception:
            capture["extracted_filters"] = {}

    # Diagnostic search only if PostgreSQL search was executed and returned 0 products
    if capture["search_calls"] and capture["search_calls"][-1]["result_count"] == 0:
        actual_filters = capture["search_calls"][-1]["filters"]
        candidates: list[tuple[str, dict[str, Any]]] = []
        if actual_filters.get("query"):
            candidates.append(("same filters without free-text term", {**actual_filters, "query": None}))
        for label, diagnostic_filters in candidates:
            try:
                matches = original_search(**diagnostic_filters)
                capture["diagnostic_searches"].append({
                    "purpose": label,
                    "filters": diagnostic_filters,
                    "match_count": len(matches),
                })
            except Exception as exc:
                capture["diagnostic_searches"].append({
                    "purpose": label,
                    "filters": diagnostic_filters,
                    "error": f"{type(exc).__name__}: {exc}",
                })

    # Classify the outcome into cases A, B, C, D
    # A. Production intentionally returns a deterministic catalog response without Ollama.
    # B. Production actually calls Ollama and receives a response.
    # C. Production attempts Ollama but Ollama fails.
    # D. Evaluator/capture code fails.
    case_type: str
    evaluation_status: str
    error: str | None = None

    if capture.get("evaluator_error"):
        case_type = "D"
        evaluation_status = "evaluator_error"
        error = capture["evaluator_error"]
    elif pipeline_failed:
        case_type = "pipeline_error"
        evaluation_status = "failed_during_pipeline"
        error = capture.get("error") or "ChatService pipeline raised unhandled exception"
    elif capture["actual_ollama_called"]:
        if capture.get("ollama_failure"):
            case_type = "C"
            evaluation_status = "failed_during_generation"
            error = f"Ollama generation failed: {capture['ollama_failure']}"
            capture["response_source"] = "fallback_after_ollama_error"
        elif capture.get("response_source") == "ollama":
            case_type = "B"
            evaluation_status = "success"
            error = None
        else:
            case_type = "C"
            evaluation_status = "failed_during_generation"
            error = "Ollama was called but returned fallback response"
    else:
        # Ollama was not called
        if (
            service._response_source == "deterministic_catalog"
            or timings.get("ollama_skipped_reason") == "deterministic_catalog_search"
        ):
            case_type = "A"
            evaluation_status = "deterministic_catalog"
            capture["response_source"] = "deterministic_catalog"
            error = None
        elif isinstance(capture["laya_confidence"], (int, float)) and capture["laya_confidence"] < 0.15:
            case_type = "clarification"
            evaluation_status = "clarification_requested"
            capture["response_source"] = "clarification"
            error = f"Laya confidence ({capture['laya_confidence']}) below threshold (0.15); clarification requested."
        elif capture["laya_intent"] == "cart_action" and not capture["search_calls"]:
            case_type = "cart_empty"
            evaluation_status = "empty_cart_response"
            capture["response_source"] = "cart_fallback"
            error = "Cart was empty; prompt returned empty cart guidance."
        elif capture.get("selected_product_found") is False:
            case_type = "product_not_found"
            evaluation_status = "product_not_found"
            capture["response_source"] = "clarification"
            error = "Product lookup returned no matching product in catalog."
        else:
            case_type = "not_called"
            evaluation_status = "not_called"
            capture["response_source"] = service._response_source or "not_called"
            error = "ChatService returned without calling Ollama."

    searches = capture["search_calls"]
    product_search_result_count = searches[-1]["result_count"] if searches else None

    return {
        "id": case["id"],
        "question": case["user_input"],
        "laya_intent": capture["laya_intent"],
        "laya_confidence": capture["laya_confidence"],
        "intent_action": action,
        "extracted_filters": capture["extracted_filters"],
        "product_search_result_count": product_search_result_count,
        "actual_ollama_called": capture["actual_ollama_called"],
        "ollama_failure": capture.get("ollama_failure"),
        "final_response_received": capture["final_response_received"],
        "timings": timings,
        "case_classification": case_type,
        "retrieved_contexts": capture["retrieved_contexts"],
        "reference_contexts": capture["reference_contexts"],
        "response": response_text,
        "response_source": capture["response_source"],
        "evaluation_status": evaluation_status,
        "error": error,
        "search_calls": capture["search_calls"],
        "diagnostic_searches": capture["diagnostic_searches"],
    }


def print_pipeline_trace(row: dict[str, Any]) -> None:
    """Print one compact stage-by-stage diagnostic for every dataset query."""
    print(
        "PIPELINE TRACE\n"
        f"  QUERY: {row.get('question')}\n"
        f"  LAYA CHOICE: {row.get('laya_intent')}\n"
        f"  LAYA CONFIDENCE: {row.get('laya_confidence')}\n"
        f"  INTENT/ACTION: {row.get('intent_action')}\n"
        f"  EXTRACTED FILTERS: {json.dumps(row.get('extracted_filters'), ensure_ascii=False, sort_keys=True)}\n"
        f"  PRODUCT SEARCH RESULT COUNT: {row.get('product_search_result_count') if row.get('product_search_result_count') is not None else 'search not run'}\n"
        f"  ACTUAL OLLAMA CALLED: {row.get('actual_ollama_called')}\n"
        f"  OLLAMA FAILURE: {row.get('ollama_failure') or 'none'}\n"
        f"  FINAL RESPONSE RECEIVED: {row.get('final_response_received')}\n"
        f"  CASE CLASSIFICATION: Case {row.get('case_classification')}\n"
        f"  RESPONSE SOURCE: {row.get('response_source')}\n"
        f"  FAILURE/STOP REASON: {row.get('error') or 'none'}\n"
        f"  TIMINGS: {json.dumps(row.get('timings'), ensure_ascii=False, sort_keys=True)}",
        flush=True,
    )


async def score_with_ragas(
    rows: list[dict[str, Any]], selected_metrics: set[str] | None = None
) -> list[dict[str, Any]]:
    """Score with Ragas 0.4 collections metrics and Ollama's OpenAI-compatible API."""
    from openai import AsyncOpenAI
    from app.config import settings
    from ragas.embeddings.base import embedding_factory
    from ragas.llms import llm_factory
    from ragas.metrics.collections import (
        AnswerRelevancy,
        ContextPrecisionWithoutReference,
        ContextRecall,
        Faithfulness,
    )

    base_url = os.getenv("RAGAS_OLLAMA_BASE_URL", "https://ollama.com/v1")
    model = os.getenv("RAGAS_OLLAMA_MODEL", "gpt-oss:20b-cloud")
    embedding_model = os.getenv("RAGAS_OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
    api_key = settings.OLLAMA_API_KEY.strip()
    if not api_key:
        raise SystemExit("OLLAMA_API_KEY must be set to score with the Ollama Cloud judge.")
    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=90, max_retries=0)
    # Ragas faithfulness/recall can produce long structured outputs for product
    # contexts; the factory default of 1024 tokens truncated several valid calls.
    llm = llm_factory(model, provider="openai", client=client, max_tokens=4096)
    embedding_base_url = os.getenv(
        "RAGAS_OLLAMA_EMBEDDING_BASE_URL", "http://localhost:11434/v1"
    )
    embedding_client = AsyncOpenAI(
        api_key="ollama", base_url=embedding_base_url, timeout=90, max_retries=0
    )
    embeddings = embedding_factory(
        "openai", model=embedding_model, client=embedding_client, interface="modern"
    )
    metrics = {
        "faithfulness": Faithfulness(llm=llm),
        "answer_relevancy": AnswerRelevancy(llm=llm, embeddings=embeddings),
        "context_precision": ContextPrecisionWithoutReference(llm=llm),
        "context_recall": ContextRecall(llm=llm),
    }
    if selected_metrics is not None:
        unknown = selected_metrics - set(metrics)
        if unknown:
            raise SystemExit(f"Unknown Ragas metrics: {', '.join(sorted(unknown))}")
        metrics = {name: metric for name, metric in metrics.items() if name in selected_metrics}

    scored: list[dict[str, Any]] = []
    for index, row in enumerate(rows, 1):
        output = dict(row)
        for key in metrics:
            output[key] = None

        if row.get("case_classification") == "A":
            output["evaluation_note"] = (
                "Case A: Production intentionally returned deterministic catalog response without Ollama; excluded from quality scoring."
            )
            scored.append(output)
            continue

        if row.get("case_classification") == "C":
            output["evaluation_note"] = (
                f"Case C: Ollama generation failed ({row.get('ollama_failure')}); excluded from quality scoring."
            )
            scored.append(output)
            continue

        if row.get("case_classification") == "D":
            output["evaluation_note"] = (
                f"Case D: Evaluator error ({row.get('error')}); excluded from quality scoring."
            )
            scored.append(output)
            continue

        if row.get("evaluation_status") != "success" or row.get("response_source") != "ollama":
            output["evaluation_note"] = row.get("error") or "Response did not come from Ollama generation path."
            scored.append(output)
            continue

        if not row.get("retrieved_contexts"):
            output["evaluation_note"] = "No retrieved catalog context; context-dependent metrics not scored."
            scored.append(output)
            continue

        async def score_one(name: str, metric: Any) -> tuple[str, float | None, str | None]:
            if name == "context_recall" and not row.get("reference_contexts"):
                return name, None, None
            try:
                kwargs: dict[str, Any] = {
                    "user_input": row["question"],
                }
                if name in ("faithfulness", "answer_relevancy", "context_precision"):
                    kwargs["response"] = row["response"]
                if name in ("faithfulness", "context_precision", "context_recall"):
                    kwargs["retrieved_contexts"] = row["retrieved_contexts"]
                if name == "context_recall":
                    kwargs["reference"] = "\n".join(row["reference_contexts"])
                result = await metric.ascore(**kwargs)
                if isinstance(result.value, (int, float)) and math.isfinite(result.value):
                    return name, result.value, None
                return name, None, "Ragas returned a non-finite score."
            except Exception as exc:
                return name, None, f"{type(exc).__name__}: {str(exc)[:500]}"

        metric_results = await asyncio.gather(
            *(score_one(name, metric) for name, metric in metrics.items())
        )
        for name, value, error in metric_results:
            if value is not None:
                output[name] = value
            elif error:
                output.setdefault("metric_errors", {})[name] = error
        print(f"Scored {index}/{len(rows)}: {row['question']}")
        scored.append(output)
    return scored


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--score-captured", action="store_true",
        help="Re-score responses and contexts already captured in results/chat_responses.json without calling ShopAI again.",
    )
    parser.add_argument(
        "--capture-only", action="store_true",
        help="Run all dataset prompts through the real ChatService and save raw captures without invoking Ragas yet.",
    )
    parser.add_argument(
        "--metrics", nargs="+",
        choices=("faithfulness", "answer_relevancy", "context_precision", "context_recall"),
        help="Optionally run only selected metrics; by default all four are attempted.",
    )
    args = parser.parse_args()
    cases = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    if not cases:
        raise SystemExit("Dataset is empty.")
    if args.score_captured:
        if not CAPTURE_JSON.exists():
            raise SystemExit(f"No raw pipeline captures found at {CAPTURE_JSON}")
        rows = json.loads(CAPTURE_JSON.read_text(encoding="utf-8"))
    else:
        rows = []
        db = SessionLocal()
        try:
            for case in cases:
                print(f"Running actual ShopAI pipeline: {case['user_input']}")
                row = asyncio.run(capture_case(db, case))
                rows.append(row)
                print_pipeline_trace(row)
        finally:
            db.close()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CAPTURE_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.capture_only:
        actual_ollama_count = sum(row.get("response_source") == "ollama" for row in rows)
        print(f"Captured {len(rows)} cases ({actual_ollama_count} Ollama generations): {CAPTURE_JSON}")
        return
    selected_metrics = set(args.metrics) if args.metrics else None
    scored = asyncio.run(score_with_ragas(rows, selected_metrics))
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_JSON.write_text(json.dumps(scored, ensure_ascii=False, indent=2), encoding="utf-8")
    columns = [
        "id", "question", "laya_intent", "laya_confidence", "intent_action",
        "product_search_result_count", "actual_ollama_called", "ollama_failure",
        "final_response_received", "case_classification", "response", "response_source",
        "evaluation_status", "error", "search_calls", "diagnostic_searches",
        "retrieved_contexts", "reference_contexts", "timings", "faithfulness", "answer_relevancy",
        "context_precision", "context_recall", "evaluation_note", "metric_errors",
    ]
    with RESULTS_CSV.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in scored:
            flattened = dict(row)
            for field in (
                "retrieved_contexts", "reference_contexts", "metric_errors",
                "search_calls", "diagnostic_searches", "extracted_filters", "timings",
            ):
                flattened[field] = json.dumps(row.get(field), ensure_ascii=False) if row.get(field) else ""
            writer.writerow(flattened)

    metric_names = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")
    averages = {
        name: (sum(row[name] for row in scored if isinstance(row.get(name), (int, float)) and math.isfinite(row[name])) /
               sum(isinstance(row.get(name), (int, float)) and math.isfinite(row[name]) for row in scored))
        if any(isinstance(row.get(name), (int, float)) and math.isfinite(row[name]) for row in scored) else None
        for name in metric_names
    }
    case_counts = {
        "A_deterministic_catalog": sum(row.get("case_classification") == "A" for row in rows),
        "B_ollama_success": sum(row.get("case_classification") == "B" for row in rows),
        "C_ollama_failure": sum(row.get("case_classification") == "C" for row in rows),
        "D_evaluator_error": sum(row.get("case_classification") == "D" for row in rows),
    }
    actual_ollama_responses = sum(row.get("response_source") == "ollama" for row in rows)
    eligible_rows = sum(
        row.get("evaluation_status") == "success" and row.get("response_source") == "ollama"
        for row in rows
    )
    scored_counts = {
        name: sum(isinstance(row.get(name), (int, float)) and math.isfinite(row[name]) for row in scored)
        for name in metric_names
    }
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_count": len(cases),
        "actual_ollama_responses": actual_ollama_responses,
        "cases": case_counts,
        "metrics": averages,
        "scored_rows": scored_counts,
        "eligible_ollama_rows": eligible_rows,
        "metric_coverage": {
            name: f"{scored_counts[name]}/{eligible_rows}"
            for name in metric_names
        },
        "metrics_evaluated": [name for name, count in scored_counts.items() if count],
        "metrics_unavailable": [name for name, count in scored_counts.items() if not count],
        "metrics_partial": [
            name for name, count in scored_counts.items() if 0 < count < eligible_rows
        ],
        "failures": [
            {
                "id": row.get("id"),
                "question": row.get("question"),
                "case_classification": row.get("case_classification"),
                "error": row.get("error"),
                "ollama_failure": row.get("ollama_failure"),
            }
            for row in rows
            if row.get("case_classification") in ("C", "D", "pipeline_error")
        ],
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Results: {RESULTS_CSV}")


if __name__ == "__main__":
    main()
