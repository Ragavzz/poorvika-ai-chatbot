"""Read-only integration smoke test; no accuracy or benchmark claims."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = Path(__file__).resolve().parent
PROMPTS = ["Show me Samsung phones under ₹20000", "Recommend a good phone for gaming", "Tell me the price of this product", "Add this phone to cart", "Show my cart", "Which phone has the best camera?", "Hello"]


def call(port, payload):
    start = time.perf_counter()
    try:
        request = Request(f"http://127.0.0.1:{port}/decide", data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=120) as response:
            output = json.loads(response.read())
            status = response.status
        answer = output.get("raw", output).get("answers", {}).get("intent", {})
        return {"status": status, "decision": answer.get("choice"), "confidence": answer.get("confidence"), "probabilities": answer.get("probabilities"), "http_latency_ms": (time.perf_counter() - start) * 1000, "output": output}
    except (HTTPError, URLError, TimeoutError) as error:
        return {"error": str(error), "http_latency_ms": (time.perf_counter() - start) * 1000}


def main():
    questions = json.loads((BASE / "shopai_questions.json").read_text(encoding="utf-8"))
    rows = []
    for prompt in PROMPTS:
        payload = {"state": {"message": prompt}, "questions": questions}
        row = {"prompt": prompt, "input": payload, "old_5055": call(5055, payload), "v2_5056": call(5056, payload)}
        rows.append(row)
        print(json.dumps({"prompt": prompt, **{key: {k: v for k, v in row[key].items() if k not in {"output", "probabilities"}} for key in ("old_5055", "v2_5056")}}, ensure_ascii=False), flush=True)
    folder = BASE / "results"
    folder.mkdir(exist_ok=True)
    output = folder / ("comparison_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ") + ".json")
    with output.open("x", encoding="utf-8") as file:
        json.dump({"kind": "integration smoke test; not accuracy benchmark", "cases": rows}, file, indent=2, ensure_ascii=False)
    print(f"Full inputs, probabilities, structures and outputs: {output}")


if __name__ == "__main__":
    main()
