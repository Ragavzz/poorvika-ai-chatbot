"""Isolated endpoint config for the copied baseline runner."""
from pathlib import Path
import sys

EXPERIMENT_DIR = Path(__file__).resolve().parent
BENCHMARK_DIR = EXPERIMENT_DIR.parent
if str(BENCHMARK_DIR) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_DIR))

DATASET_JSON = BENCHMARK_DIR / "dataset" / "typed_decisions_test.json"
DATASET_PARQUET = BENCHMARK_DIR / "dataset" / "test-00000-of-00001.parquet"
RESULTS_DIR = BENCHMARK_DIR / "results"
LAYA_BASE_URL = "http://127.0.0.1:5056"
LAYA_DECIDE_ENDPOINT = f"{LAYA_BASE_URL}/decide"
LAYA_HEALTH_ENDPOINT = f"{LAYA_BASE_URL}/health"
LAYA_REQUEST_TIMEOUT = 60
