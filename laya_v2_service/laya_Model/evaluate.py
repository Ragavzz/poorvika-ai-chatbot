import os
import time
import json
import argparse
import numpy as np
import pandas as pd
from datasets import load_dataset
import laya
from laya.common import ece_score

def evaluate_model(model_path_or_id: str, device: str = "cuda", output_json: str = "benchmark_report.json"):
    print(f"=== Loading Test Split (LocalLLaMA/typed-decisions) ===")
    ds_test = load_dataset("LocalLLaMA/typed-decisions", "all", split="test")

    print(f"=== Initializing Agent: {model_path_or_id} (device: {device}) ===")
    agent = laya.Agent(model_path_or_id, device=device)

    predictions = []
    latencies_ms = []

    print(f"Evaluating {len(ds_test)} test cases (2,000 decisions)...")
    t0_eval = time.time()

    for i, row in enumerate(ds_test):
        case_id = row["id"]
        workflow = row["workflow"]
        state = json.loads(row["state"])
        questions = json.loads(row["questions"])
        gold = json.loads(row["gold"])

        t0 = time.perf_counter()
        res = agent.predict(state, questions)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(dt_ms)

        predictions.append({
            "id": case_id,
            "workflow": workflow,
            "pred": res["answers"],
            "gold": gold,
            "questions": questions,
            "latency_ms": dt_ms
        })

    eval_total_time = time.time() - t0_eval
    print(f"Evaluated {len(ds_test)} cases in {eval_total_time:.1f}s ({len(ds_test)/eval_total_time:.2f} cases/s)!")

    # Calculate metrics
    accuracies = []
    soft_accuracies = []
    brier_scores = []
    kl_divs = []
    tv_distances = []
    score_maes = []
    within_one = []
    all_confs = []
    all_corrects = []

    for item in predictions:
        pred_answers = item["pred"]
        gold_answers = item["gold"]
        questions = item["questions"]

        for qid, qdef in questions.items():
            p_ans = pred_answers[qid]
            g_ans = gold_answers[qid]
            q_type = qdef["type"]

            # 1. Choice
            if q_type == "choice":
                keys = list(qdef["criteria"].keys())
                pred_choice = p_ans["choice"]
                gold_label = str(g_ans["label"])

                is_corr = float(pred_choice == gold_label)
                accuracies.append(is_corr)
                all_corrects.append(is_corr)

                p_probs = np.array([p_ans["probabilities"].get(k, 1e-6) for k in keys])
                g_probs = np.array([g_ans["probabilities"].get(k, 1e-6) for k in keys])
                p_probs /= p_probs.sum()
                g_probs /= g_probs.sum()

                all_confs.append(float(p_probs.max()))
                soft_accuracies.append(float((p_probs * g_probs).sum()))
                brier_scores.append(float(((p_probs - g_probs) ** 2).sum()))
                tv_distances.append(float(0.5 * np.abs(p_probs - g_probs).sum()))
                kl_divs.append(float((g_probs * np.log(np.clip(g_probs, 1e-6, None) / np.clip(p_probs, 1e-6, None))).sum()))

            # 2. Noul
            elif q_type == "noul":
                p_val = p_ans["noul"]
                g_val = g_ans.get("noul", g_ans.get("probabilities", {}).get("true", 0.5))
                gold_label = str(g_ans["label"]).lower()

                pred_label = "true" if p_val >= 0.5 else "false"
                is_corr = float(pred_label == gold_label)
                accuracies.append(is_corr)
                all_corrects.append(is_corr)
                all_confs.append(float(max(p_val, 1.0 - p_val)))

                p_dist = np.array([1.0 - p_val, p_val])
                g_dist = np.array([1.0 - g_val, g_val])

                soft_accuracies.append(float((p_dist * g_dist).sum()))
                brier_scores.append(float(((p_dist - g_dist) ** 2).sum()))
                tv_distances.append(float(0.5 * np.abs(p_dist - g_dist).sum()))
                kl_divs.append(float((g_dist * np.log(np.clip(g_dist, 1e-6, None) / np.clip(p_dist, 1e-6, None))).sum()))

            # 3. Score
            elif q_type == "score":
                p_score = p_ans["score"]
                g_score = g_ans.get("score", 0.0)
                score_maes.append(abs(p_score - g_score))
                within_one.append(float(abs(p_score - g_score) <= 1.0))

                n_levels = len(qdef.get("criteria", []))
                p_probs_score = np.array([p_ans["probabilities"].get(str(i), 0.0) for i in range(n_levels)])
                if p_probs_score.sum() > 0:
                    p_probs_score /= p_probs_score.sum()
                    p_lvl = int(np.argmax(p_probs_score))
                    all_confs.append(float(p_probs_score.max()))
                else:
                    p_lvl = int(round(p_score))
                    all_confs.append(0.5)

                g_lvl = int(g_ans.get("label", int(round(g_score))))
                is_corr = float(p_lvl == g_lvl)
                accuracies.append(is_corr)
                all_corrects.append(is_corr)

    laya_acc = np.mean(accuracies)
    laya_soft_acc = np.mean(soft_accuracies)
    laya_brier = np.mean(brier_scores)
    laya_kl = np.mean(kl_divs)
    laya_tv = np.mean(tv_distances)
    laya_ece = ece_score(np.array(all_confs), np.array(all_corrects))
    laya_mae = np.mean(score_maes) if score_maes else 0.0
    laya_within1 = np.mean(within_one) if within_one else 0.0
    laya_latency = np.percentile(latencies_ms, 50)
    laya_p95 = np.percentile(latencies_ms, 95)
    laya_p99 = np.percentile(latencies_ms, 99)

    comparison_data = [
        {
            "Model": "TypeSafe Jev 1.13.0",
            "Kind": "general",
            "Accuracy": 0.727,
            "Soft Acc": 0.580,
            "Brier": 0.148,
            "ECE": 0.144,
            "Score MAE": 0.391,
            "Within 1 Level": "0.952",
            "ms/case": 710,
            "Cost/Case": "$0.0004 (API)"
        },
        {
            "Model": "Laya (Fine-Tuned Ours)",
            "Kind": "fine-tuned",
            "Accuracy": round(float(laya_acc), 3),
            "Soft Acc": round(float(laya_soft_acc), 3),
            "Brier": round(float(laya_brier), 3),
            "ECE": round(float(laya_ece), 3),
            "Score MAE": round(float(laya_mae), 3),
            "Within 1 Level": f"{laya_within1:.3f}",
            "ms/case": round(float(laya_latency), 1),
            "Cost/Case": "$0.00 (Self-Hosted)"
        },
        {
            "Model": "ModernBERT-base (149M)",
            "Kind": "specialist",
            "Accuracy": 0.646,
            "Soft Acc": 0.542,
            "Brier": 0.119,
            "ECE": 0.179,
            "Score MAE": 0.444,
            "Within 1 Level": "0.931",
            "ms/case": 349,
            "Cost/Case": "$0.00"
        },
        {
            "Model": "Teacher Self-Agreement",
            "Kind": "ceiling",
            "Accuracy": 0.735,
            "Soft Acc": "-",
            "Brier": "-",
            "ECE": "-",
            "Score MAE": "-",
            "Within 1 Level": "-",
            "ms/case": "-",
            "Cost/Case": "-"
        }
    ]

    df_comp = pd.DataFrame(comparison_data)
    print("\n=== HEAD-TO-HEAD BENCHMARK TABLE ===")
    try:
        print(df_comp.to_markdown(index=False))
    except Exception:
        print(df_comp.to_string(index=False))

    # Per-workflow breakdown
    per_wf_report = {}
    for wf in ["agent_trace_observability", "customer_service", "invoice_processing", "security_incidents"]:
        wf_items = [item for item in predictions if item["workflow"] == wf]
        wf_corr = []
        for item in wf_items:
            for qid, qdef in item["questions"].items():
                p_ans = item["pred"][qid]
                g_ans = item["gold"][qid]
                if qdef["type"] == "choice":
                    wf_corr.append(float(p_ans["choice"] == str(g_ans["label"])))
                elif qdef["type"] == "noul":
                    pred_label = "true" if p_ans["noul"] >= 0.5 else "false"
                    wf_corr.append(float(pred_label == str(g_ans["label"]).lower()))
                elif qdef["type"] == "score":
                    p_probs = [p_ans["probabilities"].get(str(i), 0.0) for i in range(len(qdef.get("criteria", [])))]
                    p_lvl = int(np.argmax(p_probs)) if sum(p_probs) > 0 else int(round(p_ans["score"]))
                    g_lvl = int(g_ans.get("label", int(round(g_ans.get("score", 0.0)))))
                    wf_corr.append(float(p_lvl == g_lvl))
        if wf_corr:
            per_wf_report[wf] = {
                "n_decisions": len(wf_corr),
                "accuracy": round(float(np.mean(wf_corr)), 4)
            }

    report = {
        "benchmark": "LocalLLaMA/typed-decisions",
        "model": str(model_path_or_id),
        "n_cases": len(ds_test),
        "n_decisions": len(ds_test) * 5,
        "metrics": {
            "accuracy": round(float(laya_acc), 4),
            "soft_accuracy": round(float(laya_soft_acc), 4),
            "brier_score": round(float(laya_brier), 4),
            "ece": round(float(laya_ece), 4),
            "score_mae": round(float(laya_mae), 4),
            "within_1_level": round(float(laya_within1), 4),
            "latency_p50_ms": round(float(laya_latency), 1),
            "latency_p95_ms": round(float(laya_p95), 1),
            "latency_p99_ms": round(float(laya_p99), 1),
            "throughput_cases_per_s": round(1000.0 / float(np.mean(latencies_ms)), 2),
            "kl_divergence": round(float(laya_kl), 4),
            "total_variation": round(float(laya_tv), 4)
        },
        "comparison": comparison_data,
        "per_workflow": per_wf_report
    }

    with open(output_json, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n[+] Benchmark report successfully saved to: {output_json}")
    print(json.dumps(report["metrics"], indent=2))

def main():
    parser = argparse.ArgumentParser(description="Evaluate fine-tuned Laya model on typed-decisions benchmark")
    parser.add_argument("--model_path", default="Mass121/laya-typed-decisions-v2", help="Local directory or HF repo ID")
    parser.add_argument("--device", default="cuda" if laya._os.environ.get("CUDA_VISIBLE_DEVICES") or laya.torch.cuda.is_available() else "cpu", help="Device for evaluation")
    parser.add_argument("--output_json", default="benchmark_report.json", help="Output path for benchmark report")
    args = parser.parse_args()

    evaluate_model(args.model_path, device=args.device, output_json=args.output_json)

if __name__ == "__main__":
    main()
