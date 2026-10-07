# Opt-in ShopAI decision service

This entry point uses the verified local specialist bundle without copying it. `LAYA_MODEL=base` (default) or `LAYA_MODEL=specialist` selects the model. The legacy `npm start` entry point is unchanged; no permanent production default is changed.

Run these commands in three terminals from the repository root. Separate ports avoid replacing running services. Each terminal needs its own environment values.

Specialist decision layer:

```powershell
$env:LAYA_MODEL='specialist'; $env:PORT='5056'
node laya_service/switchable_server.mjs
```

Existing FastAPI app, real configured PostgreSQL catalog and existing Ollama configuration:

```powershell
$env:TESTING_MODE='false'; $env:LAYA_DECIDE_URL='http://127.0.0.1:5056/decide'
$env:DATASET_PATH=(Resolve-Path data/poorvika_products.jsonl).Path
& .venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8001 --log-level info
```

Existing React frontend:

```powershell
$env:VITE_API_BASE_URL='http://127.0.0.1:8001'
npm --prefix frontend run dev -- --host 127.0.0.1 --port 3000 --strictPort
```

To select base, stop only the decision layer, then run:

```powershell
$env:LAYA_MODEL='base'; $env:PORT='5056'
node laya_service/switchable_server.mjs
```

Open `http://127.0.0.1:3000`, an origin already allowed by the backend CORS configuration. The backend/frontend commands stay the same. No automatic fallback is enabled: inference failure is HTTP 500 with identity, `inference_success:false`, and `fallback:false`. Model load/hash failure stops startup. The backend retains its existing error handling and action disambiguation; no new intent rules are added. Startup verifies all specialist bundle file hashes and its 1024/256 context configuration; `/health` reports revision, hashes and actual configuration. Every answer is logged with model/revision/type/choice/confidence/probabilities/latency/fallback.

Bundle: `evaluation/laya_specialist_onnx_isolated/bundle/`.
Revision: `1a793eb568e6718f15941d08f85432581df534e3`.
ONNX SHA-256: `e2b4eeeb1347a94680839a0bdcd473de53c151ab6134193c82ba525459c59474`.
Source weights SHA-256: `4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e`.

Live PostgreSQL/API validation and 20 warm requests:

```powershell
& .venv/Scripts/python.exe evaluation/laya_specialist_onnx_isolated/integration/live_validate.py
```

The live validator uses a read-only PostgreSQL preflight, verifies an existing nonempty catalog, and starts the unchanged backend and frontend on separate ports. It never uses a SQLite test host or synthetic catalog. API cart contexts test transport only; they do not establish real browser persistence/synchronization. Browser verification must be recorded separately. Existing backend test failures are reported without altering tests to force a pass. No full JEV benchmark is run.

The current backend `.env` dataset path is missing on this machine, although PostgreSQL already has the real catalog. The explicit DATASET_PATH above points to the existing workspace catalog; it does not change catalog bytes or database data. The unchanged backend unit tests still contain older expected catalog counts/stock and run product search against SQLite without PostgreSQL's strpos function; report those failures rather than changing assertions or catalog data.
