"""Benchmark metrics calculation for LocalLLaMA typed-decisions.

Implements official metric definitions:
- Accuracy: overall, by type (choice, score, noul), and by workflow
- Calibration:
  - Brier score (squared error between predicted distribution and gold)
  - Expected Calibration Error (ECE, 10 bins)
  - KL divergence from gold (Kullback-Leibler divergence)
- Score specifics: Mean Absolute Error (MAE) and Root Mean Squared Error (RMSE) on score
- Latency: Mean, Median (P50), P95, P99
"""

import math
from typing import Any, Dict, List, Optional


def calculate_accuracy(correct_flags: List[bool]) -> float:
    """Calculates accuracy given a list of boolean match flags."""
    if not correct_flags:
        return 0.0
    return sum(1 for c in correct_flags if c) / len(correct_flags)


def calculate_brier_score(decisions: List[Dict[str, Any]]) -> float:
    """Calculates the mean Brier score across all evaluated decisions.

    For each decision, computes sum of squared differences between predicted
    and gold probabilities:
        Brier_i = (1 / K) * sum_k (p_k - g_k)^2
    where K is the number of options/outcomes.
    Lower is better.
    """
    scores = []
    for d in decisions:
        pred_probs = d.get("pred_probabilities") or {}
        gold_probs = d.get("gold_probabilities") or {}
        if not pred_probs or not gold_probs:
            continue

        # Collect union of keys
        all_keys = set(pred_probs.keys()) | set(gold_probs.keys())
        if not all_keys:
            continue

        k = len(all_keys)
        sq_err = sum((pred_probs.get(key, 0.0) - gold_probs.get(key, 0.0)) ** 2 for key in all_keys)
        # Using 1/K normalization
        scores.append(sq_err / k)

    return sum(scores) / len(scores) if scores else 0.0


def calculate_brier_score_hard(decisions: List[Dict[str, Any]]) -> float:
    """Calculates multi-class Brier score against one-hot gold label.

    Brier_i = (1 / 2) * sum_k (p_k - y_k)^2 where y_k = 1 for gold label.
    """
    scores = []
    for d in decisions:
        pred_probs = d.get("pred_probabilities") or {}
        gold_label = str(d.get("gold_label"))
        if not pred_probs or gold_label is None:
            continue

        all_keys = set(pred_probs.keys()) | {gold_label}
        sq_err = sum(
            (pred_probs.get(key, 0.0) - (1.0 if str(key) == gold_label else 0.0)) ** 2
            for key in all_keys
        )
        scores.append(0.5 * sq_err)

    return sum(scores) / len(scores) if scores else 0.0


def calculate_ece(decisions: List[Dict[str, Any]], num_bins: int = 10) -> float:
    """Calculates Expected Calibration Error (ECE).

    Bins confidence into equal intervals [0, 0.1), [0.1, 0.2), ... [0.9, 1.0].
    ECE = sum_b (|B_b| / N) * |acc(B_b) - conf(B_b)|
    """
    valid_decisions = [
        d for d in decisions
        if d.get("confidence") is not None and d.get("correct") is not None
    ]
    n = len(valid_decisions)
    if n == 0:
        return 0.0

    bins = [[] for _ in range(num_bins)]
    for d in valid_decisions:
        conf = float(d["confidence"])
        conf = min(max(conf, 0.0), 1.0)
        bin_idx = int(conf * num_bins)
        if bin_idx == num_bins:
            bin_idx = num_bins - 1
        bins[bin_idx].append(d)

    ece = 0.0
    for b in bins:
        if not b:
            continue
        bin_size = len(b)
        bin_acc = sum(1 for d in b if d["correct"]) / bin_size
        bin_conf = sum(float(d["confidence"]) for d in b) / bin_size
        ece += (bin_size / n) * abs(bin_acc - bin_conf)

    return ece


def calculate_kl_divergence(decisions: List[Dict[str, Any]], epsilon: float = 1e-7) -> float:
    """Calculates mean KL divergence KL(gold || pred) across decisions.

    KL(g || p) = sum_k g_k * log((g_k + eps) / (p_k + eps))
    Lower is better.
    """
    kl_values = []
    for d in decisions:
        pred_probs = d.get("pred_probabilities") or {}
        gold_probs = d.get("gold_probabilities") or {}
        if not pred_probs or not gold_probs:
            continue

        all_keys = set(pred_probs.keys()) | set(gold_probs.keys())
        if not all_keys:
            continue

        kl = 0.0
        for k in all_keys:
            g_k = float(gold_probs.get(k, 0.0))
            p_k = float(pred_probs.get(k, 0.0))
            if g_k > 0:
                kl += g_k * math.log((g_k + epsilon) / (p_k + epsilon))

        kl_values.append(max(0.0, kl))

    return sum(kl_values) / len(kl_values) if kl_values else 0.0


def calculate_percentile(values: List[float], p: float) -> float:
    """Computes p-th percentile of values."""
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_v[int(k)]
    d0 = sorted_v[int(f)] * (c - k)
    d1 = sorted_v[int(c)] * (k - f)
    return d0 + d1


def calculate_latency_metrics(latencies_ms: List[float]) -> Dict[str, float]:
    """Computes mean, median (p50), p95, and p99 latency in ms."""
    if not latencies_ms:
        return {"mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0}

    return {
        "mean_ms": round(sum(latencies_ms) / len(latencies_ms), 2),
        "p50_ms": round(calculate_percentile(latencies_ms, 50), 2),
        "p95_ms": round(calculate_percentile(latencies_ms, 95), 2),
        "p99_ms": round(calculate_percentile(latencies_ms, 99), 2),
    }


def compute_all_benchmark_metrics(decisions: List[Dict[str, Any]], case_latencies_ms: List[float]) -> Dict[str, Any]:
    """Computes comprehensive summary metrics across all benchmark decisions."""
    total_decisions = len(decisions)
    successful_decisions = [d for d in decisions if d.get("error") is None]
    failed_decisions = [d for d in decisions if d.get("error") is not None]

    # Overall accuracy
    overall_correct = [d["correct"] for d in successful_decisions if d.get("correct") is not None]
    overall_accuracy = calculate_accuracy(overall_correct)

    # By Decision Type
    type_metrics = {}
    for dtype in ["choice", "score", "noul"]:
        type_decs = [d for d in successful_decisions if d.get("decision_type") == dtype]
        correct_flags = [d["correct"] for d in type_decs if d.get("correct") is not None]
        acc = calculate_accuracy(correct_flags)
        brier = calculate_brier_score(type_decs)
        ece = calculate_ece(type_decs)
        kl = calculate_kl_divergence(type_decs)

        t_res = {
            "total": len(type_decs),
            "accuracy": round(acc, 4),
            "brier_score": round(brier, 4),
            "ece": round(ece, 4),
            "kl_from_gold": round(kl, 4),
        }

        if dtype == "score":
            mae_vals = [d["score_error"] for d in type_decs if d.get("score_error") is not None]
            within_1 = [d["within_1_level"] for d in type_decs if d.get("within_1_level") is not None]
            t_res["mae"] = round(sum(mae_vals) / len(mae_vals), 4) if mae_vals else None
            t_res["within_1_accuracy"] = round(calculate_accuracy(within_1), 4) if within_1 else None

        type_metrics[dtype] = t_res

    # By Workflow
    workflow_metrics = {}
    for wf in sorted(set(d.get("workflow", "") for d in decisions if d.get("workflow"))):
        wf_decs = [d for d in successful_decisions if d.get("workflow") == wf]
        correct_flags = [d["correct"] for d in wf_decs if d.get("correct") is not None]
        acc = calculate_accuracy(correct_flags)
        brier = calculate_brier_score(wf_decs)
        ece = calculate_ece(wf_decs)
        kl = calculate_kl_divergence(wf_decs)

        # Accuracy by type inside workflow
        wf_choice = calculate_accuracy([d["correct"] for d in wf_decs if d.get("decision_type") == "choice"])
        wf_score = calculate_accuracy([d["correct"] for d in wf_decs if d.get("decision_type") == "score"])
        wf_noul = calculate_accuracy([d["correct"] for d in wf_decs if d.get("decision_type") == "noul"])

        workflow_metrics[wf] = {
            "total_decisions": len(wf_decs),
            "overall_accuracy": round(acc, 4),
            "choice_accuracy": round(wf_choice, 4),
            "score_accuracy": round(wf_score, 4),
            "noul_accuracy": round(wf_noul, 4),
            "brier_score": round(brier, 4),
            "ece": round(ece, 4),
            "kl_from_gold": round(kl, 4),
        }

    # Calibration across all decisions
    overall_brier = calculate_brier_score(successful_decisions)
    overall_brier_hard = calculate_brier_score_hard(successful_decisions)
    overall_ece = calculate_ece(successful_decisions)
    overall_kl = calculate_kl_divergence(successful_decisions)

    # Latencies
    case_latency_stats = calculate_latency_metrics(case_latencies_ms)
    decision_latencies_ms = [lat / 5.0 for lat in case_latencies_ms]  # 5 decisions per case
    decision_latency_stats = calculate_latency_metrics(decision_latencies_ms)

    return {
        "benchmark": "LocalLLaMA/typed-decisions",
        "split": "test",
        "total_cases_evaluated": len(case_latencies_ms),
        "total_decisions_evaluated": total_decisions,
        "successful_decisions": len(successful_decisions),
        "failed_decisions": len(failed_decisions),
        "overall_accuracy": round(overall_accuracy, 4),
        "choice_accuracy": type_metrics.get("choice", {}).get("accuracy", 0.0),
        "score_accuracy": type_metrics.get("score", {}).get("accuracy", 0.0),
        "score_mae": type_metrics.get("score", {}).get("mae"),
        "score_within_1_level_accuracy": type_metrics.get("score", {}).get("within_1_accuracy"),
        "noul_accuracy": type_metrics.get("noul", {}).get("accuracy", 0.0),
        "brier_score": round(overall_brier, 4),
        "brier_score_hard_labels": round(overall_brier_hard, 4),
        "ece": round(overall_ece, 4),
        "kl_from_gold": round(overall_kl, 4),
        "case_latency_ms": case_latency_stats,
        "decision_latency_ms": decision_latency_stats,
        "by_decision_type": type_metrics,
        "by_workflow": workflow_metrics,
    }
