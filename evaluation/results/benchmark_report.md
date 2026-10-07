# Poorvika ShopAI Comprehensive Pipeline Benchmark Report
**Execution Timestamp:** 2026-10-03 14:25:33 UTC  
**Evaluator:** Standalone ShopAI Benchmark Suite  
**Pipeline Components:** Laya ONNX System-1 Decision Layer, PostgreSQL Catalog (508 products), Local Ollama LLM (llama3.2:latest)  
**Test Set:** 58 realistic shopping queries across 12 categories  

---

## Executive Benchmark Summary

| Benchmark Domain | Key Metric | Measured Result | Target / Baseline | Status |
|---|---|---|---|---|
| **1. Laya Intent Accuracy** | Overall Accuracy | **67.2%** | >= 85.0% | REVIEW |
| **1. Laya Intent F1** | Macro F1-Score | **0.5126** | >= 0.80 | REVIEW |
| **2. Confidence Calibration** | Expected Calibration Error (ECE) | **0.1685** | <= 0.1500 | MISCALIBRATED |
| **3. Product Retrieval** | Top-1 Accuracy | **64.3%** | >= 80.0% | REVIEW |
| **3. Filter Accuracy** | Brand & Price Accuracy | **96.8% / 100.0%** | 100.0% | PASS |
| **4. Response Grounding** | Grounded Response Rate | **54.0%** | >= 75.0% | PASS |
| **4. Unsupported Claims** | Unsupported Claim Rate | **8.1%** | 0.0% | WARNING |
| **5. End-to-End Latency** | Mean Total Latency | **1869.6 ms** | Baseline: 0.0 ms | NORMAL |
| **6. Reliability** | Pipeline Success Rate | **100.0%** | >= 98.0% | PASS |
| **7. Repeatability** | Intent Consistency Rate | **100.0%** | 100.0% | PASS |

---

## Benchmark 1: Laya Intent Classification Quality

- **Total Queries Evaluated:** 58
- **Correct Predictions:** 39
- **Overall Intent Accuracy:** 67.24%
- **Macro Average:** Precision = 0.5745, Recall = 0.6152, F1 = 0.5126
- **Weighted Average:** Precision = 0.8713, Recall = 0.6724, F1 = 0.7090
- **Average Laya Decision Latency:** 1460.72 ms

### Per-Intent Performance Metrics

| Intent Class | Support | Accuracy | Precision | Recall | F1-Score | TP | FP | FN |
|---|---|---|---|---|---|---|---|---|
| `add_to_cart` | 4 | 100.0% | 0.3636 | 1.0000 | 0.5333 | 4 | 7 | 0 |
| `cart_action` | 4 | 100.0% | 0.3333 | 1.0000 | 0.5000 | 4 | 8 | 0 |
| `general_query` | 11 | 36.4% | 1.0000 | 0.3636 | 0.5333 | 4 | 0 | 7 |
| `product_details` | 5 | 60.0% | 0.7500 | 0.6000 | 0.6667 | 3 | 1 | 2 |
| `product_search` | 33 | 72.7% | 1.0000 | 0.7273 | 0.8421 | 24 | 0 | 9 |
| `recommendation` | 1 | 0.0% | 0.0000 | 0.0000 | 0.0000 | 0 | 3 | 1 |


### Confusion Matrix (Rows = Ground Truth, Columns = Predicted Laya Choice)

| True \ Pred | `add_to_cart` | `cart_action` | `general_query` | `product_details` | `product_search` | `recommendation` |
|---|---|---|---|---|---|---|
| `add_to_cart` | 4 | 0 | 0 | 0 | 0 | 0 |
| `cart_action` | 0 | 4 | 0 | 0 | 0 | 0 |
| `general_query` | 6 | 0 | 4 | 1 | 0 | 0 |
| `product_details` | 0 | 0 | 0 | 3 | 0 | 2 |
| `product_search` | 0 | 8 | 0 | 0 | 24 | 1 |
| `recommendation` | 1 | 0 | 0 | 0 | 0 | 0 |

---

## Benchmark 2: Laya Confidence Calibration

- **Expected Calibration Error (ECE):** **0.1685**
- **Maximum Calibration Error (MCE):** **0.3281**
- **Calibration Status:** Moderately calibrated (0.10 <= ECE < 0.20)

| Confidence Range | Predictions Count | Empirical Accuracy | Average Confidence | Calibration Gap |
|---|---|---|---|---|
| `0.0-0.2` | 11 | 18.2% | 13.4% | 0.0481 |
| `0.2-0.4` | 16 | 62.5% | 29.8% | 0.3271 |
| `0.4-0.6` | 10 | 70.0% | 51.5% | 0.1852 |
| `0.6-0.8` | 6 | 100.0% | 67.2% | 0.3281 |
| `0.8-1.0` | 15 | 93.3% | 92.0% | 0.0128 |


> **Calibration Finding:** Laya confidence shows significant variance relative to observed accuracy. Confidence values should be interpreted cautiously.

---

## Benchmark 3: Product Retrieval Accuracy (PostgreSQL Single Source of Truth)

- **Total Retrieval Queries Evaluated:** 28
- **Top-1 Accuracy:** 64.29%
- **Top-3 Accuracy:** 75.00%
- **Top-5 Accuracy:** 75.00%

### Precision@K and Recall@K

| Metric | K = 1 | K = 3 | K = 5 |
|---|---|---|---|
| **Precision@K** | 0.7500 | 0.8095 | 0.8143 |
| **Recall@K** | 0.3571 | 0.5714 | 0.5893 |


### SQL Filter Constraint Verification

| Filter Dimension | Evaluated Items | Verified Accuracy | Compliance |
|---|---|---|---|
| **Category Filter** | 65 | 89.23% | Exact mapping to PostgreSQL catalog |
| **Brand Filter** | 31 | 96.77% | Case-insensitive token match |
| **Maximum Price Filter** | 28 | 100.00% | Guaranteed price <= max_price |
| **Minimum Price Filter** | 4 | 100.00% | Guaranteed price >= min_price |
| **Stock / Availability Filter** | 0 | 100.00% | In-stock flag enforcement |

---

## Benchmark 4: Final Response Correctness and Grounding

- **Evaluated Responses:** 37
- **Factual Correctness Rate:** **56.76%**
- **Grounded Response Rate:** **54.05%**
- **Unsupported Claim Rate:** **8.11%**

### Response Classification Breakdown

| Classification Class | Count | Percentage | Description |
|---|---|---|---|
| **Correct** | 20 | 54.1% | All product names, prices, MRP, and stock match PostgreSQL ground truth |
| **Partially correct** | 1 | 2.7% | Relevant products cited without false pricing |
| **Incorrect** | 13 | 35.1% | Response makes an inaccurate factual claim about a database entity |
| **Unsupported / hallucinated** | 3 | 8.1% | Invented pricing or products not found in PostgreSQL |

---

## Benchmark 5: End-to-End Latency Breakdown & Baseline Comparison

### Pipeline Stage Percentiles (Milliseconds)

| Component / Stage | Mean (ms) | Median (ms) | Min (ms) | Max (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|---|
| **Total Pipeline Request** | 1869.6 | 1346.0 | 1229.0 | 15573.7 | 2814.6 | 15573.7 |
| **Laya Decision Layer** | 1460.7 | 1332.6 | 1224.0 | 6101.6 | 1769.4 | 6101.6 |
| **PostgreSQL Query Tool** | 8.2 | 5.5 | 2.2 | 63.5 | 13.2 | 63.5 |
| **Ollama LLM Generation** | 2119.2 | 989.5 | 563.7 | 13922.9 | 13922.9 | 13922.9 |
| **Backend Overhead / Routing** | 2.3 | 2.0 | 0.6 | 10.6 | 7.0 | 10.6 |


### Comparison with Baseline (`laya_vs_bypass_2026-09-30.csv`)

| Metric Dimension | Measured Live Run | Baseline (Laya Enabled) | Delta / Change |
|---|---|---|---|
| **Total Latency Mean** | 1869.6 ms | 0.0 ms | +1869.6 ms |
| **Laya Latency Mean** | 1460.7 ms | 0.0 ms | +1460.7 ms |
| **PostgreSQL Latency Mean** | 8.2 ms | 0.0 ms | +8.2 ms |

---

## Benchmark 6: System Reliability and Failure Breakdown

- **Total Evaluated Requests:** 58
- **Successful Requests:** 58
- **Success Rate:** **100.00%**
- **Error Rate:** **0.00%**

### Failure Reasons Breakdown

| Failure Category | Occurrences | Percentage | Impact Description |
|---|---|---|---|
| **Laya Decision Failure** | 0 | 0.0% | Service unreachable or uncalibrated fallback rejected |
| **PostgreSQL Query Failure** | 0 | 0.0% | Database connection pool dropped or syntax exception |
| **Ollama Service Failure** | 0 | 0.0% | Local LLM inference failed or model unloaded |
| **Request Timeout** | 0 | 0.0% | Processing exceeded 45.0s window |
| **Invalid Response Format** | 0 | 0.0% | Schema deserialization failure |
| **Unexpected Exception** | 0 | 0.0% | Uncaught server runtime error |

---

## Benchmark 7: Execution Repeatability & Consistency Analysis

- **Queries Tested:** 10 (each repeated 5 times = 50 runs)
- **Intent Consistency Rate:** **100.0%**
- **Product Retrieval Consistency Rate:** **100.0%**
- **Response Consistency Rate:** **100.0%**

### Per-Query Repeatability Details

| Query | Intent Consistency | Product Consistency | Response Consistency | Mean Latency | Latency CV |
|---|---|---|---|---|---|
| `Do you have wireless earphones?` | 100.0% | 100.0% | 100.0% | 1383.6 ms | 6.0% |
| `Tell me about Sony MDR-EX15AP` | 100.0% | 100.0% | 100.0% | 2091.1 ms | 12.9% |
| `Add this phone to my cart` | 100.0% | 100.0% | 100.0% | 1339.7 ms | 2.7% |
| `Show my cart` | 100.0% | 100.0% | 100.0% | 1749.1 ms | 13.3% |
| `Hello` | 100.0% | 100.0% | 100.0% | 1805.3 ms | 7.4% |
| `Which products are available under ...` | 100.0% | 100.0% | 100.0% | 1391.9 ms | 8.3% |
| `Show me Sony earphones under ₹1000` | 100.0% | 100.0% | 100.0% | 1352.3 ms | 4.4% |
| `Show me Samsung phones under 30000` | 100.0% | 100.0% | 100.0% | 1351.7 ms | 4.0% |
| `Do you sell Gucci shoes?` | 100.0% | 100.0% | 100.0% | 1319.9 ms | 2.9% |
| `I want something nice` | 100.0% | 100.0% | 100.0% | 1275.1 ms | 3.2% |

---

## How to Reproduce This Benchmark

Ensure the 3 Poorvika ShopAI services are running:

1. **Laya Decision Service**: `node server.js` (port 5055)

2. **PostgreSQL Database**: PostgreSQL on localhost:5432 with `shopai` database

3. **Ollama Service**: `ollama serve` (port 11434 with `llama3.2`)


Run the benchmark runner directly from PowerShell:

```powershell
.\.venv\Scripts\python.exe evaluation\benchmark_runner.py --all
```
