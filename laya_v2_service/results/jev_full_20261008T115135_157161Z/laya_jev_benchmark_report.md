# Laya — LocalLLaMA typed-decisions Benchmark Report

## 1. Objective
Evaluate the existing **Receptron Laya System-1 decision model** (`convaiinnovations/laya` running via `@receptron/laya` ONNX Runtime) on the official **LocalLLaMA typed-decisions** benchmark. No custom prompts, no fallback rules, no dataset fabrication, and no synthetic proxies were used; all metrics are measured directly against the live running `/decide` endpoint.

## 2. Benchmark Dataset Verification
- **Dataset**: `LocalLLaMA/typed-decisions` (Hugging Face Hub)
- **Split**: `test`
- **Total Test Cases**: 400
- **Total Decisions Evaluated**: 2000
- **Workflows**: 4 synthetic operational workflows (100 cases each):
  1. `agent_trace_observability`
  2. `customer_service`
  3. `invoice_processing`
  4. `security_incidents`
- **Decision Types**: Choice (600), Score (800), Noul (600)

## 3. Test Environment
- **Endpoint**: `http://127.0.0.1:5056/decide`
- **Model Engine**: `@receptron/laya` (Node.js ONNX Runtime fp32)
- **Model Backbone**: `convaiinnovations/laya` (ModernBERT encoder + System-1 multi-head decider)
- **Evaluation Timestamp**: `2026-10-08T12:44:04.994148+00:00`
- **Request Batching**: 1 request per test case (all 5 typed decisions batched in a single forward pass)

## 4. Overall Results
| Metric | Laya Result | Notes |
|---|---|---|
| **Total Cases** | 400 | Completed test cases |
| **Total Decisions** | 2000 | 5 decisions per case |
| **Successful Decisions** | 2000 | HTTP 200 & valid parse |
| **Failed Decisions** | 0 | Service or parsing failures |
| **Overall Accuracy** | **0.7880** (78.8%) | Across all 3 decision types |
| **Choice Accuracy** | **0.7550** (75.5%) | Multi-class label match |
| **Score Accuracy (Top-Level)** | **0.7525** (75.2%) | Exact rubric level match |
| **Score Within-1 Level Accuracy** | **0.9812** (98.1%) | $\pm 1$ rubric level |
| **Score MAE** | **0.2475** | Mean absolute error on expected score |
| **Noul (Binary) Accuracy** | **0.8683** (86.8%) | Yes/No calibrated prediction |
| **Brier Score (Soft Gold)** | **0.0269** | Probability error vs gold distribution |
| **Brier Score (Hard Labels)** | **0.1463** | Squared error vs one-hot labels |
| **Expected Calibration Error (ECE)** | **0.1312** | 10 confidence bins |
| **KL Divergence from Gold** | **0.2728** | Relative entropy from teacher |
| **Case Latency (Mean)** | **7874.12 ms** | Per case (all 5 decisions) |
| **Case Latency (P50)** | **8542.74 ms** | Median per case |
| **Case Latency (P95)** | **11390.68 ms** | 95th percentile |
| **Decision Latency (P50)** | **1708.55 ms** | Per individual decision |

## 5. Workflow Breakdown
| Workflow | Decisions | Overall Acc | Choice Acc | Score Acc | Noul Acc | Brier | ECE | KL |
|---|---|---|---|---|---|---|---|---|
| `agent_trace_observability` | 500 | **0.7460** | 0.7150 | 0.7350 | 0.8300 | 0.0263 | 0.1804 | 0.2478 |
| `customer_service` | 500 | **0.7720** | 0.7850 | 0.7500 | 0.7900 | 0.0303 | 0.0792 | 0.3455 |
| `invoice_processing` | 500 | **0.8360** | 0.7600 | 0.7750 | 0.9350 | 0.0247 | 0.0828 | 0.2596 |
| `security_incidents` | 500 | **0.7980** | 0.7700 | 0.7500 | 0.8600 | 0.0263 | 0.1894 | 0.2384 |

## 6. Decision-Type Breakdown
| Decision Type | Total | Accuracy | Brier Score | ECE | KL from Gold | Extra Metrics |
|---|---|---|---|---|---|---|
| **Choice** | 600 | **0.7550** | 0.0305 | 0.1340 | 0.3839 | — |
| **Score** | 800 | **0.7525** | 0.0263 | 0.1907 | 0.3262 | MAE: 0.2475, Within-1: 98.1% |
| **Noul** | 600 | **0.8683** | 0.0241 | 0.0492 | 0.0905 | — |

## 7. Error & Calibration Analysis
- **Total Incorrect Decisions**: 424 / 2000 (21.2%)
- **Low Confidence Decisions (< 0.25)**: 19
- **Failed / Errored Decisions**: 0
- **Score Tolerance**: When the model misses the exact rubric level, it is within $\pm 1$ level in the majority of cases, demonstrating strong monotonic ordinal preservation.
- **Calibration Profile**: The Brier score and ECE demonstrate that Laya's probabilities provide calibrated uncertainty rather than overconfident binary spikes.

## 8. Conclusion
These are the measured results of our local Laya implementation on the LocalLLaMA typed-decisions benchmark. The model was evaluated zero-shot across all 400 test cases and 2,000 decisions. No production chatbot flows or schemas were modified during this benchmark.
