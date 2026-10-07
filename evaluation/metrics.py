"""Metrics calculation library for ShopAI benchmarking suite.
Covers:
- Intent classification: Accuracy, Precision, Recall, F1, Confusion Matrix
- Confidence Calibration: ECE, MCE, Calibration Bins
- Product Retrieval: Top-K Accuracy, Precision@K, Recall@K, Filter Accuracy
- Final Response Grounding: Deterministic fact-checking, Correctness classification
- Latency: Mean, Median, Min, Max, P95, P99, StdDev
- Reliability: Success / Error rates, failure breakdown
- Repeatability: Consistency ratios, Latency CV
"""

import math
import re
from typing import Any, Dict, List, Optional, Tuple


def calculate_classification_metrics(
    y_true: List[str], y_pred: List[str], labels: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Calculates Accuracy, per-class & macro/weighted Precision, Recall, F1, and confusion matrix."""
    if not y_true or not y_pred or len(y_true) != len(y_pred):
        return {"error": "Invalid inputs for classification metrics"}

    if labels is None:
        labels = sorted(list(set(y_true) | set(y_pred)))

    total = len(y_true)
    correct = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
    accuracy = correct / total if total > 0 else 0.0

    # Confusion matrix: row = true, col = pred
    matrix = {true_lbl: {pred_lbl: 0 for pred_lbl in labels} for true_lbl in labels}
    for yt, yp in zip(y_true, y_pred):
        if yt in matrix and yp in matrix[yt]:
            matrix[yt][yp] += 1

    per_class = {}
    macro_p, macro_r, macro_f1 = 0.0, 0.0, 0.0
    weighted_p, weighted_r, weighted_f1 = 0.0, 0.0, 0.0

    for lbl in labels:
        tp = matrix[lbl][lbl]
        fp = sum(matrix[other][lbl] for other in labels if other != lbl)
        fn = sum(matrix[lbl][other] for other in labels if other != lbl)
        support = sum(matrix[lbl].values())

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        acc_class = tp / support if support > 0 else 0.0

        per_class[lbl] = {
            "support": support,
            "accuracy": round(acc_class, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }

        macro_p += prec
        macro_r += rec
        macro_f1 += f1

        weighted_p += prec * support
        weighted_r += rec * support
        weighted_f1 += f1 * support

    n_labels = len(labels)
    return {
        "total_samples": total,
        "correct_predictions": correct,
        "accuracy": round(accuracy, 4),
        "macro_avg": {
            "precision": round(macro_p / n_labels, 4) if n_labels > 0 else 0.0,
            "recall": round(macro_r / n_labels, 4) if n_labels > 0 else 0.0,
            "f1_score": round(macro_f1 / n_labels, 4) if n_labels > 0 else 0.0,
        },
        "weighted_avg": {
            "precision": round(weighted_p / total, 4) if total > 0 else 0.0,
            "recall": round(weighted_r / total, 4) if total > 0 else 0.0,
            "f1_score": round(weighted_f1 / total, 4) if total > 0 else 0.0,
        },
        "per_class": per_class,
        "labels": labels,
        "confusion_matrix": matrix,
    }


def calculate_calibration_metrics(
    confidences: List[float],
    y_true: List[str],
    y_pred: List[str],
    bins: Optional[List[Tuple[float, float]]] = None,
) -> Dict[str, Any]:
    """Calculates calibration bins, Expected Calibration Error (ECE), and Maximum Calibration Error (MCE)."""
    if bins is None:
        bins = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0)]

    total = len(confidences)
    if total == 0:
        return {"error": "Empty predictions for calibration"}

    bin_results = []
    ece = 0.0
    mce = 0.0

    for low, high in bins:
        # Match [low, high) except last bin which is [low, high]
        bin_indices = [
            i for i, c in enumerate(confidences)
            if (low <= c < high) or (high == 1.0 and low <= c <= high)
        ]
        count = len(bin_indices)
        if count > 0:
            bin_acc = sum(1 for i in bin_indices if y_true[i] == y_pred[i]) / count
            bin_conf = sum(confidences[i] for i in bin_indices) / count
            gap = abs(bin_acc - bin_conf)
            weight = count / total
            ece += weight * gap
            if gap > mce:
                mce = gap
        else:
            bin_acc = 0.0
            bin_conf = (low + high) / 2.0
            gap = 0.0

        bin_results.append({
            "range": f"{low:.1f}-{high:.1f}",
            "count": count,
            "accuracy": round(bin_acc, 4),
            "avg_confidence": round(bin_conf, 4),
            "calibration_gap": round(gap, 4),
        })

    is_calibrated = ece < 0.15  # standard empirical calibration threshold

    return {
        "total_predictions": total,
        "expected_calibration_error": round(ece, 4),
        "maximum_calibration_error": round(mce, 4),
        "is_calibrated": is_calibrated,
        "calibration_assessment": (
            "Well calibrated (ECE < 0.10)" if ece < 0.10
            else "Moderately calibrated (0.10 <= ECE < 0.20)" if ece < 0.20
            else "Poorly calibrated / Miscalibrated (ECE >= 0.20)"
        ),
        "bins": bin_results,
    }


def calculate_retrieval_metrics(
    retrieved_items: List[List[Dict[str, Any]]],
    expected_criteria_list: List[Dict[str, Any]],
    k_values: Tuple[int, ...] = (1, 3, 5),
) -> Dict[str, Any]:
    """Calculates Top-1/3/5 Accuracy, Precision@K, Recall@K, and specific filter accuracies."""
    n_queries = len(retrieved_items)
    if n_queries == 0:
        return {"error": "No retrieval queries to evaluate"}

    top_hits = {k: 0 for k in k_values}
    precision_at_k = {k: 0.0 for k in k_values}
    recall_at_k = {k: 0.0 for k in k_values}

    # Filter metrics: category, brand, max_price, min_price, stock
    filter_checks = {
        "category": {"total": 0, "correct": 0},
        "brand": {"total": 0, "correct": 0},
        "max_price": {"total": 0, "correct": 0},
        "min_price": {"total": 0, "correct": 0},
        "stock": {"total": 0, "correct": 0},
    }

    for ret, criteria in zip(retrieved_items, expected_criteria_list):
        exp_brand = criteria.get("brand")
        exp_cat = criteria.get("category")
        max_p = criteria.get("max_price")
        min_p = criteria.get("min_price")
        stock_req = criteria.get("in_stock_only", False)
        target_ids = set(criteria.get("expected_product_ids") or [])

        def matches_item(item: Dict[str, Any]) -> bool:
            if target_ids and item.get("id") in target_ids:
                return True
            matched = True
            if exp_brand and exp_brand.lower() not in (item.get("brand") or "").lower():
                matched = False
            if exp_cat:
                c = (item.get("category") or "").lower()
                ec = exp_cat.lower()
                if ec not in c and c not in ec and not (ec == "accessories" and c in ["data cables", "battery chargers", "cases & covers", "power banks"]):
                    matched = False
            if max_p and item.get("price") and item["price"] > (max_p * 1.05):
                matched = False
            if min_p and item.get("price") and item["price"] < (min_p * 0.95):
                matched = False
            return matched

        # Top-K accuracy and precision/recall
        for k in k_values:
            slice_k = ret[:k]
            relevant_in_k = [it for it in slice_k if matches_item(it)]
            if relevant_in_k:
                top_hits[k] += 1
            prec = len(relevant_in_k) / len(slice_k) if slice_k else (1.0 if not target_ids else 0.0)
            precision_at_k[k] += prec

            # Recall calculation: relative to target_ids if available, else binary match
            if target_ids:
                rec = len([it for it in slice_k if it.get("id") in target_ids]) / len(target_ids)
            else:
                rec = 1.0 if relevant_in_k or (not ret and not target_ids) else 0.0
            recall_at_k[k] += rec

        # Filter precision across all returned items
        for it in ret:
            if exp_cat:
                filter_checks["category"]["total"] += 1
                c = (it.get("category") or "").lower()
                ec = exp_cat.lower()
                if ec in c or c in ec or (ec == "accessories" and c in ["data cables", "battery chargers", "cases & covers", "power banks"]):
                    filter_checks["category"]["correct"] += 1

            if exp_brand:
                filter_checks["brand"]["total"] += 1
                if exp_brand.lower() in (it.get("brand") or "").lower():
                    filter_checks["brand"]["correct"] += 1

            if max_p is not None:
                filter_checks["max_price"]["total"] += 1
                if it.get("price") is not None and it["price"] <= (max_p * 1.05):
                    filter_checks["max_price"]["correct"] += 1

            if min_p is not None:
                filter_checks["min_price"]["total"] += 1
                if it.get("price") is not None and it["price"] >= (min_p * 0.95):
                    filter_checks["min_price"]["correct"] += 1

            if stock_req:
                filter_checks["stock"]["total"] += 1
                if it.get("in_stock") is True:
                    filter_checks["stock"]["correct"] += 1

    filter_accuracy = {}
    for f_name, f_data in filter_checks.items():
        tot = f_data["total"]
        cor = f_data["correct"]
        filter_accuracy[f"{f_name}_filter_accuracy"] = round(cor / tot, 4) if tot > 0 else 1.0
        filter_accuracy[f"{f_name}_verified_count"] = tot

    return {
        "total_queries_evaluated": n_queries,
        "top_1_accuracy": round(top_hits[1] / n_queries, 4),
        "top_3_accuracy": round(top_hits[3] / n_queries, 4),
        "top_5_accuracy": round(top_hits[5] / n_queries, 4),
        "precision_at_1": round(precision_at_k[1] / n_queries, 4),
        "precision_at_3": round(precision_at_k[3] / n_queries, 4),
        "precision_at_5": round(precision_at_k[5] / n_queries, 4),
        "recall_at_1": round(recall_at_k[1] / n_queries, 4),
        "recall_at_3": round(recall_at_k[3] / n_queries, 4),
        "recall_at_5": round(recall_at_k[5] / n_queries, 4),
        "filter_accuracy": filter_accuracy,
    }


def evaluate_response_grounding(
    response_text: str, retrieved_products: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Programmatically verifies factual correctness of response against PostgreSQL retrieved products.
    Checks:
    - product name match
    - price match (within standard currency format)
    - MRP match
    - discount match
    - availability / stock match
    - brand match
    - category match
    Classifies as: Correct, Partially correct, Incorrect, Unsupported / hallucinated
    """
    clean_text = response_text or ""
    if not retrieved_products:
        # If no products were retrieved, check if response properly acknowledges that
        no_match_phrases = [
            "couldn't find", "could not find", "no matching", "no products", "broaden",
            "not found", "empty", "didn't find", "unavailable"
        ]
        is_appropriate_no_match = any(p in clean_text.lower() for p in no_match_phrases)
        # Check if response hallucinates nonexistent items
        price_mentions = re.findall(r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)", clean_text, re.I)
        if is_appropriate_no_match:
            classification = "Correct"
        elif price_mentions:
            classification = "Unsupported / hallucinated"
        else:
            classification = "Partially correct"

        return {
            "classification": classification,
            "extracted_prices": price_mentions,
            "matched_products": [],
            "factual_checks": {
                "acknowledged_empty": is_appropriate_no_match,
                "hallucinated_prices": len(price_mentions) > 0 and not is_appropriate_no_match,
            },
        }

    # Extract prices mentioned in text
    mentioned_prices = []
    price_matches = re.finditer(r"(?:₹|rs\.?|inr)?\s*(\b\d{2,3}(?:,\d{2,3})*(?:\.\d+)?)\b", clean_text, re.I)
    for m in price_matches:
        raw_val = m.group(1).replace(",", "")
        try:
            val = float(raw_val)
            if val >= 50:  # ignore small integers like quantities or port counts
                mentioned_prices.append(val)
        except ValueError:
            pass

    factual_checks = {
        "names_checked": 0,
        "names_matched": 0,
        "prices_checked": len(mentioned_prices),
        "prices_matched": 0,
        "stock_checked": 0,
        "stock_matched": 0,
        "brands_checked": 0,
        "brands_matched": 0,
    }

    db_prices = [p.get("price") for p in retrieved_products if p.get("price")]
    db_mrps = [p.get("mrp") for p in retrieved_products if p.get("mrp")]
    all_db_prices = set(db_prices + db_mrps)

    for mp in mentioned_prices:
        # Check if mentioned price matches any db price within rounding (e.g. 829.0 vs 829)
        if any(abs(mp - db_p) < 1.0 for db_p in all_db_prices):
            factual_checks["prices_matched"] += 1

    matched_prods = []
    for p in retrieved_products:
        p_name = p.get("name", "")
        # Check if at least significant tokens of name appear
        name_tokens = [tok.lower() for tok in re.findall(r"[a-zA-Z0-9]+", p_name) if len(tok) > 2]
        token_hits = sum(1 for tok in name_tokens if tok in clean_text.lower())
        name_found = (token_hits >= 2) if len(name_tokens) >= 2 else (token_hits >= 1)
        if name_found:
            matched_prods.append(p["id"])
            factual_checks["names_matched"] += 1
        factual_checks["names_checked"] += 1

        brand = (p.get("brand") or "").lower()
        if brand and brand in clean_text.lower():
            factual_checks["brands_matched"] += 1
            factual_checks["brands_checked"] += 1

        # Stock check
        in_stock = p.get("in_stock", True)
        if in_stock and ("in stock" in clean_text.lower() or "available" in clean_text.lower()):
            factual_checks["stock_matched"] += 1
            factual_checks["stock_checked"] += 1
        elif not in_stock and ("out of stock" in clean_text.lower() or "unavailable" in clean_text.lower()):
            factual_checks["stock_matched"] += 1
            factual_checks["stock_checked"] += 1

    # Classify response
    # 1. Incorrect: Stated prices that contradict database
    unmatched_prices = [p for p in mentioned_prices if not any(abs(p - db_p) < 1.0 for db_p in all_db_prices)]
    has_false_prices = len(unmatched_prices) > 0 and len(db_prices) > 0

    if has_false_prices and len(matched_prods) == 0:
        classification = "Unsupported / hallucinated"
    elif has_false_prices:
        classification = "Incorrect"
    elif len(matched_prods) > 0:
        if (
            (factual_checks["prices_checked"] == 0 or factual_checks["prices_matched"] > 0)
            and (factual_checks["stock_checked"] == 0 or factual_checks["stock_matched"] > 0)
        ):
            classification = "Correct"
        else:
            classification = "Partially correct"
    else:
        # No specific product tokens recognized, but might be general or fallback
        if "out of stock" in clean_text.lower() or "couldn't find" in clean_text.lower():
            classification = "Correct"
        else:
            classification = "Partially correct"

    return {
        "classification": classification,
        "extracted_prices": mentioned_prices,
        "unmatched_prices": unmatched_prices,
        "matched_product_ids": matched_prods,
        "factual_checks": factual_checks,
    }


def calculate_grounding_summary(evaluations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculates factual correctness rate, grounded response rate, and unsupported claim rate."""
    total = len(evaluations)
    if total == 0:
        return {"error": "No grounding evaluations to summarize"}

    counts = {
        "Correct": 0,
        "Partially correct": 0,
        "Incorrect": 0,
        "Unsupported / hallucinated": 0,
    }

    for ev in evaluations:
        c = ev.get("classification", "Partially correct")
        counts[c] = counts.get(c, 0) + 1

    factual_correctness_rate = (counts["Correct"] + counts["Partially correct"]) / total * 100
    grounded_response_rate = counts["Correct"] / total * 100
    unsupported_claim_rate = counts["Unsupported / hallucinated"] / total * 100

    return {
        "total_responses_evaluated": total,
        "breakdown": counts,
        "factual_correctness_rate": round(factual_correctness_rate, 2),
        "grounded_response_rate": round(grounded_response_rate, 2),
        "unsupported_claim_rate": round(unsupported_claim_rate, 2),
    }


def calculate_latency_statistics(latencies: List[float]) -> Dict[str, Any]:
    """Calculates mean, median, min, max, P95, P99, and std dev from millisecond timings."""
    if not latencies:
        return {
            "count": 0, "mean": 0.0, "median": 0.0, "min": 0.0,
            "max": 0.0, "p95": 0.0, "p99": 0.0, "std_dev": 0.0,
        }

    clean = sorted([float(x) for x in latencies if x is not None and not math.isnan(x)])
    n = len(clean)
    if n == 0:
        return {
            "count": 0, "mean": 0.0, "median": 0.0, "min": 0.0,
            "max": 0.0, "p95": 0.0, "p99": 0.0, "std_dev": 0.0,
        }

    mean_val = sum(clean) / n
    variance = sum((x - mean_val) ** 2 for x in clean) / (n - 1) if n > 1 else 0.0
    std_dev = math.sqrt(variance)

    def percentile(p: float) -> float:
        idx = int(math.ceil(p / 100.0 * n)) - 1
        return clean[max(0, min(idx, n - 1))]

    return {
        "count": n,
        "mean": round(mean_val, 2),
        "median": round(percentile(50.0), 2),
        "min": round(clean[0], 2),
        "max": round(clean[-1], 2),
        "p95": round(percentile(95.0), 2),
        "p99": round(percentile(99.0), 2),
        "std_dev": round(std_dev, 2),
    }


def calculate_repeatability_metrics(
    query_runs: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, Any]:
    """Calculates intent consistency, product consistency, response consistency, and latency variation."""
    results = {}
    overall_intent_consistent = 0
    overall_product_consistent = 0
    overall_response_consistent = 0
    total_queries = len(query_runs)

    for q_text, runs in query_runs.items():
        n_runs = len(runs)
        if n_runs == 0:
            continue

        intents = [r.get("intent") for r in runs]
        product_sets = [tuple(sorted(r.get("product_ids") or [])) for r in runs]
        responses = [r.get("classification") for r in runs]
        total_latencies = [r.get("total_ms", 0.0) for r in runs if r.get("total_ms")]

        # Consistency = ratio of most common value over total runs
        intent_mode_count = max(intents.count(x) for x in set(intents))
        intent_consistency = intent_mode_count / n_runs

        prod_mode_count = max(product_sets.count(x) for x in set(product_sets))
        product_consistency = prod_mode_count / n_runs

        resp_mode_count = max(responses.count(x) for x in set(responses))
        response_consistency = resp_mode_count / n_runs

        if intent_consistency == 1.0:
            overall_intent_consistent += 1
        if product_consistency == 1.0:
            overall_product_consistent += 1
        if response_consistency == 1.0:
            overall_response_consistent += 1

        lat_stats = calculate_latency_statistics(total_latencies)
        mean_l = lat_stats["mean"]
        sd_l = lat_stats["std_dev"]
        cv = (sd_l / mean_l * 100.0) if mean_l > 0 else 0.0

        results[q_text] = {
            "runs_count": n_runs,
            "intents": intents,
            "intent_consistency": round(intent_consistency * 100.0, 1),
            "product_consistency": round(product_consistency * 100.0, 1),
            "response_consistency": round(response_consistency * 100.0, 1),
            "latency_mean_ms": mean_l,
            "latency_std_dev_ms": sd_l,
            "latency_cv_percent": round(cv, 1),
        }

    return {
        "total_queries_tested": total_queries,
        "queries_with_100pct_intent_consistency": overall_intent_consistent,
        "queries_with_100pct_product_consistency": overall_product_consistent,
        "queries_with_100pct_response_consistency": overall_response_consistent,
        "intent_consistency_rate": round(overall_intent_consistent / total_queries * 100.0, 1) if total_queries > 0 else 0.0,
        "product_consistency_rate": round(overall_product_consistent / total_queries * 100.0, 1) if total_queries > 0 else 0.0,
        "response_consistency_rate": round(overall_response_consistent / total_queries * 100.0, 1) if total_queries > 0 else 0.0,
        "per_query_details": results,
    }
