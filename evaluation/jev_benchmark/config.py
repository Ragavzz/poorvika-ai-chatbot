"""Configuration for LocalLLaMA typed-decisions benchmark on Laya."""

from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"
DATASET_PARQUET = DATASET_DIR / "test-00000-of-00001.parquet"
DATASET_JSON = DATASET_DIR / "typed_decisions_test.json"
RESULTS_DIR = BASE_DIR / "results"

# Laya Service Configuration
# Uses the user's existing running Laya decision service
LAYA_BASE_URL = "http://localhost:5055"
LAYA_DECIDE_ENDPOINT = f"{LAYA_BASE_URL}/decide"
LAYA_HEALTH_ENDPOINT = f"{LAYA_BASE_URL}/health"
LAYA_REQUEST_TIMEOUT = 60  # seconds

# Benchmark Constants
BENCHMARK_NAME = "LocalLLaMA/typed-decisions"
SPLIT = "test"
TOTAL_CASES = 400
TOTAL_DECISIONS = 2000
WORKFLOWS = [
    "agent_trace_observability",
    "customer_service",
    "invoice_processing",
    "security_incidents",
]
DECISION_TYPES = ["choice", "score", "noul"]
