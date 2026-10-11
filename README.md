# Poorvika ShopAI

React/TanStack Start storefront with a FastAPI shopping chatbot, PostgreSQL catalog, pinned Python Laya V2 decisions and optional Ollama generation. Search/details/recommendations format actual retrieved catalog rows. Cart operations update the client cart; checkout is currently simulated.

**Start with the [final technical handover](documentation/FINAL_PROJECT_HANDOVER.md).** It identifies implemented features, verified results, historical experiments and unresolved production requirements.

- [Architecture and request diagrams](documentation/ARCHITECTURE.md)
- [API reference](documentation/API_REFERENCE.md)
- [Windows setup, configuration and operations](documentation/DEPLOYMENT_AND_OPERATIONS.md)
- [Tests, benchmarks and evidence](documentation/TESTING_AND_BENCHMARKS.md)

## Prerequisites

Tested locally: Node 22.14.0, Python 3.13.3, PostgreSQL 18.6. Use Node 22.14 to satisfy current lockfile engine requirements. Backend dependency minimums are not a reproducible lock. Frontend uses npm package-lock.json; V2 has its own Python environment and dependency constraints.

Create environments/configuration using the [clean-checkout guide](documentation/DEPLOYMENT_AND_OPERATIONS.md#clean-checkout--powershell). Keep backend/.env and frontend/.env private. Set VITE_API_BASE_URL=http://localhost:8000 and privately configure PostgreSQL. Run from the specified cwd so a relative DATASET_PATH resolves correctly.

A clean clone does **not** contain model weights. Provision the approved V2 cache and llama3.2:latest separately; do not silently switch checkpoints or download models as part of a documentation check.

## Local startup

Run in separate terminals. Commands assume the repository root unless noted.

```powershell
# Python Laya V2: existing, complete approved cache only
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
& ./laya_v2_service/.venv/Scripts/python.exe -u ./laya_v2_service/service.py
```

```powershell
# Use the existing Ollama daemon if already running
ollama serve
```

```powershell
# Backend
Set-Location backend
& ../.venv/Scripts/python.exe run.py
```

```powershell
# Frontend
Set-Location frontend
npm.cmd run dev -- --host 127.0.0.1 --port 8080 --strictPort
```

Open http://localhost:8080. Check http://127.0.0.1:8000/api/health and http://127.0.0.1:5056/health. Backend health may report SQLite fallback: verify database.type rather than status alone.

The backend expects **Mass121/laya-typed-decisions-v2**, revision **6fb41711ea5ff81097e6fc09ccebf31138b06e4d**, on 5056. Legacy laya_service/server.js on 5055 and switchable ONNX code are historical, different configurations; neither is an automatic fallback. Do not compete for 5056.

Database initialization/upsert commands write data and are documented separately in the [operations guide](documentation/DEPLOYMENT_AND_OPERATIONS.md#database-creationimport).

## Validation

From backend:

```powershell
& ../.venv/Scripts/python.exe -m unittest test_backend test_chat_regressions test_suggestions test_suggestion_click test_laya_contract test_chat_concurrency test_search_budget_regressions test_accessory_compatibility test_short_accessory
```

From frontend:

```powershell
node --test tests/chat-cart.test.cjs tests/product-suggestions.test.cjs tests/suggestion-click.test.cjs
node node_modules/typescript/bin/tsc --noEmit
node node_modules/vite/bin/vite.js build
```

From root: git diff --check.

Fresh handover checks on 10 October 2026: 138 backend executions and 18 frontend helper tests pass; TypeScript/build pass. Some tests mock models/use SQLite; real API smoke separately uses V2/PostgreSQL. Browser acceptance and production deployment/load/security remain unverified.

Historical JEV figures (35.9% base,76.5% ONNX specialist,78.8% Python V2) are separate saved experiments, not fresh inference or shopping accuracy. Read the [benchmark provenance and discrepancies](documentation/TESTING_AND_BENCHMARKS.md) before quoting them or running scripts that overwrite outputs.

Previous [Sony](documentation/sony_search_investigation_2026-10-10.md), [accessory compatibility](documentation/accessory_compatibility_investigation_2026-10-10.md) and [short-query](documentation/short_accessory_investigation_2026-10-10.md) investigations are preserved.

## Handover boundaries

Existing regex action recovery, incomplete cart/context bounds, unauthenticated ingestion, generated-prose grounding risks, simulated checkout and missing production release configuration require owner review. Model caches/environments/private .env are excluded from Git; some catalogs, a SQLite snapshot, datasets and evidence logs are already tracked. No stage/commit/push is performed by this handover task.

The final repository-wide diff check flags CRLF lines naturally appended to an existing runtime log; authored Markdown checks pass. See the handover final audit for the exact distinction.
