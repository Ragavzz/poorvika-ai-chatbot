"""Load only the requested V2 checkpoint; never substitute a model."""
import os
from pathlib import Path
os.environ["HF_HOME"] = str(Path(__file__).resolve().parent / ".cache" / "huggingface")
import json
from huggingface_hub import model_info
import laya
MODEL = "Mass121/laya-typed-decisions-v2"
info = model_info(MODEL, revision="6fb41711ea5ff81097e6fc09ccebf31138b06e4d", files_metadata=True)
print(json.dumps({"model": MODEL, "revision": info.sha, "files": [{"name": f.rfilename, "size": f.size} for f in info.siblings]}, indent=2), flush=True)
agent = laya.load(MODEL, revision="6fb41711ea5ff81097e6fc09ccebf31138b06e4d", device="cpu")
result = agent.predict({"channel": "customer_support_ticket", "ticket": "Double charged on my invoice #4921."}, {"cs_intent": {"type": "choice", "instructions": "Determine customer intent", "criteria": {"billing issue": "Billing/payment query", "technical support": "System error"}}})
print(json.dumps({"loaded": True, "model": MODEL, "raw": result}, indent=2), flush=True)
