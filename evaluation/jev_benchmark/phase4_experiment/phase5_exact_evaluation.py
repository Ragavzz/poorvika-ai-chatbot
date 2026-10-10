"""Run the untouched baseline-v2 runner against an isolated candidate endpoint."""
from __future__ import annotations

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

MODEL_ID = "convaiinnovations/laya-typed-decisions"
BASE_ENDPOINT = os.environ.get("LAYA_BASE_ENDPOINT", "http://127.0.0.1:5055")
MODEL_CHOICE = os.environ.get("LAYA_MODEL", "base")


class CandidateHandler(BaseHTTPRequestHandler):
    agent: Any = None
    revision: str | None = None
    model_choice: str = MODEL_CHOICE

    def _write_json(self, code: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        if self.path != "/health":
            self._write_json(404, {"error": "Not Found"})
            return
        if self.model_choice == "base":
            import requests
            response = requests.get(f"{BASE_ENDPOINT}/health", timeout=10)
            self._write_json(response.status_code, response.json())
            return
        self._write_json(200, {"status": "ok", "laya_loaded": True,
            "model": MODEL_ID, "revision": self.revision, "device": "cpu"})

    def do_POST(self) -> None:
        if self.path != "/decide":
            self._write_json(404, {"error": "Not Found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            if self.model_choice == "base":
                import requests
                response = requests.post(f"{BASE_ENDPOINT}/decide", json=payload, timeout=60)
                self._write_json(response.status_code, response.json())
                return
            state, questions = payload.get("state", {}), payload.get("questions", {})
            result = self.agent.predict(state, questions)
            answers = result.get("answers", result)
            if not isinstance(answers, dict):
                raise TypeError("candidate model returned no answer object")
            self._write_json(200, {"model": "laya", "answers": answers,
                "source": "official-python-laya", "checkpoint_revision": self.revision})
        except Exception as exc:
            self._write_json(500, {"error": f"{type(exc).__name__}: {exc}"})

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    import phase5_exact_runner
    import requests

    if MODEL_CHOICE not in {"base", "typed-decisions"}:
        raise ValueError("LAYA_MODEL must be 'base' or 'typed-decisions'")
    CandidateHandler.model_choice = MODEL_CHOICE
    if MODEL_CHOICE == "typed-decisions":
        import torch
        from laya import PINNED_REVISIONS, load
        torch.set_num_threads(2)
        torch.set_num_interop_threads(1)
        CandidateHandler.revision = PINNED_REVISIONS[MODEL_ID]
        CandidateHandler.agent = load(MODEL_ID, revision=CandidateHandler.revision, device="cpu")
    # The benchmark request loop is sequential. A single-threaded server avoids
    # retaining a native worker thread for each long CPU inference on Windows.
    server = HTTPServer(("127.0.0.1", 5056), CandidateHandler)
    thread = threading.Thread(target=server.serve_forever, name="phase5-candidate-http", daemon=True)
    thread.start()
    try:
        if "--smoke" in sys.argv:
            from runner import parse_laya_decision
            from config import DATASET_JSON
            cases = json.loads(DATASET_JSON.read_text(encoding="utf-8"))
            requested_id = next((arg.split("=", 1)[1] for arg in sys.argv if arg.startswith("--smoke-case=")), None)
            case = next((item for item in cases if item["case_id"] == requested_id), cases[0])
            health = requests.get("http://127.0.0.1:5056/health", timeout=10)
            health.raise_for_status()
            response = requests.post("http://127.0.0.1:5056/decide",
                json={"state": case["state"], "questions": case["questions"]}, timeout=60)
            response.raise_for_status()
            answers = response.json()["answers"]
            if set(answers) != set(case["questions"]):
                raise RuntimeError("candidate HTTP answer ids differ from the request")
            parsed = [parse_laya_decision(qid, spec, case["gold"][qid], answers[qid])
                      for qid, spec in case["questions"].items()]
            if any(row.get("error") for row in parsed):
                raise RuntimeError(f"candidate parser smoke failed: {[row['error'] for row in parsed]}")
            print(json.dumps({"smoke": "passed", "case_id": case["case_id"],
                "decisions": len(parsed), "health": health.json(), "source": response.json()["source"]}))
            return
        phase5_exact_runner.main()
    finally:
        server.shutdown()
        server.server_close()
        close = getattr(CandidateHandler.agent, "close", None) if CandidateHandler.agent else None
        if callable(close):
            close()


if __name__ == "__main__":
    main()

