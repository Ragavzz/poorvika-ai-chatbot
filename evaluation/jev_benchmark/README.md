# LocalLLaMA typed-decisions Benchmark for Laya

This module benchmarks the existing **Receptron Laya System-1 decision model** (`convaiinnovations/laya` running via `@receptron/laya` ONNX Runtime) against the official **LocalLLaMA typed-decisions** benchmark.

## Benchmark Overview
- **Dataset**: `LocalLLaMA/typed-decisions` (Hugging Face Hub)
- **Split**: `test` (400 cases, 2,000 decisions)
- **Workflows** (100 cases each):
  1. `agent_trace_observability`
  2. `customer_service`
  3. `invoice_processing`
  4. `security_incidents`
- **Decision Types**:
  - `choice` (600 decisions): Multi-option selection with probability distribution.
  - `score` (800 decisions): Ordinal rubric rating with expected score and level distributions.
  - `noul` (600 decisions): Calibrated binary P(true) decision.

## Directory Structure
```
evaluation/jev_benchmark/
├── config.py           # Configuration and endpoint settings
├── metrics.py          # Metric calculations (Accuracy, Brier, ECE, KL, Latency)
├── runner.py           # Benchmark execution engine
├── README.md           # Documentation
├── dataset/
│   ├── test-00000-of-00001.parquet  # Official benchmark test split
│   └── typed_decisions_test.json    # JSON representation
└── results/
    ├── laya_jev_benchmark_results.json  # Raw per-decision results
    ├── laya_jev_benchmark_results.csv   # Raw tabular decision data
    ├── laya_jev_benchmark_summary.json  # Aggregated metrics
    └── laya_jev_benchmark_report.md     # Official benchmark report
```

## Running the Benchmark

### 1. Small Sample Validation (5 cases = 25 decisions)
```powershell
.\.venv\Scripts\python.exe evaluation\jev_benchmark\runner.py --sample 5
```

### 2. Full Benchmark Run (400 cases = 2,000 decisions)
```powershell
.\.venv\Scripts\python.exe evaluation\jev_benchmark\runner.py --full
```

### 3. Workflow Specific Run
```powershell
.\.venv\Scripts\python.exe evaluation\jev_benchmark\runner.py --workflow customer_service
```

## Production Isolation
The benchmark runner connects directly to the existing Laya service running on `http://localhost:5055/decide`. No production chatbot code, endpoints, database schemas, or models are modified.
