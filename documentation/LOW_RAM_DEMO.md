# Low-RAM demo

The explicit `DECISION_PROVIDER=rules` mode uses a small intent resolver with the existing ChatService context, filter merging, ProductSearchTool and stock/cart checks. It does not construct LayaClient, import ModernBERT or call the Laya service. There is no automatic retry or model fallback. `OLLAMA_ENABLED=false` prevents generation requests which could load an Ollama model.

Defaults remain `DECISION_PROVIDER=laya` and `OLLAMA_ENABLED=true`. No checkpoint, weights, cache or dependency changes are required. Stop the demo backend and remove the process-local overrides to restore the model configuration later, on a suitable machine. Do not start Laya on this PC.

The current demo uses PostgreSQL (508 real products). The pre-existing database layer can use SQLite if PostgreSQL fails; verify `/api/health` explicitly says PostgreSQL before claiming PostgreSQL integration.

## Startup commands (PowerShell)

The services are already running. Do not execute these again while ports 8000 or 8080 are occupied. Commands below use separate terminals, single backend worker, no reload and a capped frontend Node heap. They do not start Laya or Ollama.

Backend:

```powershell
Set-Location 'C:\Users\GURU\OneDrive\Pictures\Documents\cubeAI solutions\poorvika-shopai'
$env:DECISION_PROVIDER = 'rules'
$env:OLLAMA_ENABLED = 'false'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$logStamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
Set-Location backend
& ../.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 *> "../lowram-backend-$logStamp.log"
```

Frontend:

```powershell
Set-Location 'C:\Users\GURU\OneDrive\Pictures\Documents\cubeAI solutions\poorvika-shopai\frontend'
$env:NODE_OPTIONS = '--max-old-space-size=384'
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000'
$logStamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
& 'C:/Program Files/nodejs/node.exe' node_modules/vite/bin/vite.js --host 127.0.0.1 --port 8080 --strictPort *> "../lowram-frontend-$logStamp.log"
```

PostgreSQL was already running; no service command was necessary. If stopped on a future run, use its existing service: `Start-Service postgresql-x64-18` (may require an administrator terminal). Check ports first with `& "$env:SystemRoot/System32/netstat.exe" -ano -p tcp`; do not terminate unknown port owners.

## Verification

From `backend`, using the existing environment:

```powershell
& ../.venv/Scripts/python.exe -m unittest test_rule_decision_provider test_chat_followups test_chat_regressions test_laya_contract test_search_budget_regressions
$env:PYTHONPATH = (Get-Location).Path
& ../.venv/Scripts/python.exe scripts/verify_lowram_demo.py
```

The live checker calls HTTP endpoints, compares results with PostgreSQL, performs no database writes and reads provider/call counts from the backend log. Its report is `lowram-demo-live-results.json`. Unit regressions use isolated fixtures; they are not evidence of live Laya validation. The original tests remain intact.

Live checks: search, Samsung follow-up with retained budget, first-product details, similar alternatives excluding selected product, real out-of-stock rejection, in-stock recommendation, cart view, greeting, unsupported checkout without mutation. Every live decision used `rule-based`, with zero Laya and Ollama calls.

Limitations: the resolver supports common shopping phrases rather than model-level language understanding. Generation is disabled; informational product questions use catalog fields, and unsupported general questions explain demo capabilities. Cart state remains frontend/session based, as before. No live Laya validation was performed. Frontend HTML returns HTTP 200; rendered browser verification was unavailable because no browser surface was connected. RAM remains very tight, so keep the demo to one browser tab; the heap cap limits Node memory but cannot guarantee total Windows memory usage.
