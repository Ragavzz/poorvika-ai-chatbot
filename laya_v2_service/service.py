"""Isolated V2 HTTP service. No ShopAI integration or alternative model."""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

os.environ["HF_HOME"] = str(Path(__file__).resolve().parent / ".cache" / "huggingface")
MODEL = "Mass121/laya-typed-decisions-v2"
REVISION = "6fb41711ea5ff81097e6fc09ccebf31138b06e4d"
CATEGORIES = {"product_search", "recommendation", "product_details", "add_to_cart", "cart_action", "general_query"}


def adapt_shopai(raw):
    """Copy genuine intent scores; unknown/non-shopping answers stay unadapted."""
    answer = raw.get("answers", {}).get("intent", {})
    if answer.get("type") != "choice" or answer.get("choice") not in CATEGORIES:
        return None
    return {
        "model": MODEL,
        "source": "laya-python-v2",
        "answers": raw["answers"],
        "decision": answer["choice"],
        "confidence": answer.get("confidence"),
        "probabilities": answer.get("probabilities"),
    }


def make_handler(agent):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, payload):
            encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            if self.path == "/health":
                self.respond(200, {"status": "ok", "model": MODEL, "revision": REVISION, "loaded": True})
            else:
                self.respond(404, {"error": "Not found"})

        def do_POST(self):
            if self.path != "/decide":
                self.respond(404, {"error": "Not found"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 1_000_000:
                    raise ValueError("Content-Length must be between 1 and 1000000 bytes")
                payload = json.loads(self.rfile.read(size).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("Body must be a JSON object")
                state, questions = payload.get("state"), payload.get("questions")
                if not isinstance(state, dict) or not isinstance(questions, dict) or not questions:
                    raise ValueError("Provide state object and non-empty questions object, as in infer.py")
                for definition in questions.values():
                    if not isinstance(definition, dict) or definition.get("type") not in {"choice", "noul", "score"}:
                        raise ValueError("Each question must define type choice, noul, or score")
            except (ValueError, UnicodeError) as error:
                self.respond(400, {"error": str(error), "model": MODEL})
                return
            try:
                start = time.perf_counter()
                with lock:
                    raw = agent.predict(state, questions)
                choices = {
                    key: {"choice": answer.get("choice"), "confidence": answer.get("confidence"), "probabilities": answer.get("probabilities")}
                    for key, answer in raw.get("answers", {}).items()
                    if answer.get("type") == "choice"
                }
                self.respond(200, {"model": MODEL, "revision": REVISION, "latency_ms": (time.perf_counter() - start) * 1000,
                                   "raw": raw, "answers": raw["answers"], "choices": choices, "shopai": adapt_shopai(raw)})
            except Exception as error:
                self.respond(500, {"error": str(error), "error_type": type(error).__name__, "model": MODEL})

    return Handler


def main():
    import laya
    print(f"Loading {MODEL}@{REVISION} on CPU once...", flush=True)
    try:
        agent = laya.load(MODEL, revision=REVISION, device="cpu")
    except Exception as error:
        raise RuntimeError(f"V2 startup failed; no fallback: {type(error).__name__}: {error}") from error
    server = ThreadingHTTPServer(("127.0.0.1", 5056), make_handler(agent))
    print("V2 loaded; listening on http://127.0.0.1:5056", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
