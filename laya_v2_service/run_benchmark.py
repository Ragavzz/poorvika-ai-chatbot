"""Call supplied evaluator without its version-dependent CLI defaults."""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
BASE = Path(__file__).resolve().parent
os.environ["HF_HOME"] = str(BASE / ".cache" / "huggingface")
sys.path.insert(0, str(BASE / "laya_Model"))
from evaluate import evaluate_model
from huggingface_hub import snapshot_download

if __name__ == "__main__":
    folder = BASE / "results"
    folder.mkdir(exist_ok=True)
    output = folder / ("benchmark_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ") + ".json")
    if output.exists():
        raise FileExistsError(output)
    checkpoint = snapshot_download("Mass121/laya-typed-decisions-v2", revision="6fb41711ea5ff81097e6fc09ccebf31138b06e4d", allow_patterns=["rl_agent_config.json", "model.safetensors", "encoder/*", "tokenizer/*"])
    evaluate_model(checkpoint, device="cpu", output_json=str(output))
