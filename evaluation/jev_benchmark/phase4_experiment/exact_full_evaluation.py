"""Run the untouched baseline-v2 runner against an isolated candidate endpoint."""
from __future__ import annotations

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

os.environ.setdefault("USE_TF", "0")

MODEL_ID = "convaiinnovations/laya-typed-decisions"


class CandidateHandler(BaseHTTPRequestHandler):
    agent: Any = None
    revision: str | None = None

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
        self._write_json(200, {"status": "ok", "laya_loaded": True,
            "model": MODEL_ID, "revision": self.revision, "device": "cpu"})

    def do_POST(self) -> None:
        if self.path != "/decide":
            self._write_json(404, {"error": "Not Found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
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
    from laya import PINNED_REVISIONS, load
    import exact_baseline_runner
    from runner import parse_laya_decision
    from config import DATASET_JSON
    import requests

    CandidateHandler.revision = PINNED_REVISIONS[MODEL_ID]
    CandidateHandler.agent = load(MODEL_ID, revision=CandidateHandler.revision, device="cpu")
    server = ThreadingHTTPServer(("127.0.0.1", 5056), CandidateHandler)
    thread = threading.Thread(target=server.serve_forever, name="phase4-candidate-http", daemon=True)
    thread.start()
    try:
        if "--smoke" in sys.argv:
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
        exact_baseline_runner.main()
    finally:
        server.shutdown()
        server.server_close()
        close = getattr(CandidateHandler.agent, "close", None)
        if callable(close):
            close()


if __name__ == "__main__":
    main()
