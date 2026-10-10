import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, "evaluation/jev_benchmark")

from runner import check_laya_health, run_benchmark

check_laya_health("http://127.0.0.1:5056/health")

output = Path("laya_v2_service/results") / (
    "jev_full_" +
    datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
)

print(f"Results directory: {output}")

run_benchmark(
    dataset_path=Path(
        "evaluation/jev_benchmark/dataset/typed_decisions_test.json"
    ),
    limit=400,
    decide_url="http://127.0.0.1:5056/decide",
    results_dir=output,
)

print(f"Benchmark completed: {output}")
