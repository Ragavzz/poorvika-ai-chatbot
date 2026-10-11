# Deployment and operations

[Main handover](FINAL_PROJECT_HANDOVER.md) · [API](API_REFERENCE.md) · [Tests/benchmarks](TESTING_AND_BENCHMARKS.md)

10 October 2026. Commands below are source-derived unless identified as freshly executed. No clean-checkout installation, production deployment, database creation/import or model provisioning was performed for this documentation task.

## Prerequisites and reproducibility

Use **Node.js 22.14.0**, the tested local version. Lockfile dependencies include Node >=22, >=22.12 and ^22.13 constraints; “Node 20+” in older setup text is insufficient. Python **3.13.3** is installed in both current environments; use Python 3.13 to reproduce this workspace. The backend has no formal requires-python or lockfile. Python syntax needs a modern Python (union annotations require >=3.10); the full dependency set on other Python versions is unverified. PostgreSQL version is not pinned by repository files. A fresh installation needs a PostgreSQL server and psycopg support.

Two Python environments are intentional: root .venv for backend/evaluation, laya_v2_service/.venv for model runtime. Frontend has npm package-lock.json v3 and also bun.lock; use npm ci for the documented path, do not mix package-manager updates. Laya model weights and environments are excluded from Git.

## Clean checkout — PowerShell

```powershell
git clone https://github.com/cubeaisolutionstech/Chatbot-laya.git
Set-Location Chatbot-laya
py -3.13 -m venv .venv
& ./.venv/Scripts/python.exe -m pip install -r ./backend/requirements.txt
if (-not (Test-Path ./backend/.env)) { Copy-Item ./backend/.env.example ./backend/.env }
if (-not (Test-Path ./frontend/.env)) { Copy-Item ./frontend/.env.example ./frontend/.env }
npm.cmd --prefix frontend ci
```

These are instructions for the next owner, **not installation evidence**. Edit the new backend environment privately: replace credential placeholders; do not commit .env. Set DATASET_PATH to an absolute existing JSONL path, or use ../data/poorvika_products.jsonl when starting from backend. The safe example labels it “relative to project root,” but runtime open() resolves a relative path against **process cwd**, not that comment. Code's default without an override is an absolute root/data path. Start commands below deliberately choose cwd.

For V2, provision the isolated environment separately:

```powershell
py -3.13 -m venv ./laya_v2_service/.venv
& ./laya_v2_service/.venv/Scripts/python.exe -m pip install -r ./laya_v2_service/requirements.txt -c ./laya_v2_service/requirements.lock.txt
```

These dependency commands may use network and are not executed here. Before starting V2, obtain the approved **Mass121/laya-typed-decisions-v2** snapshot at revision **6fb41711ea5ff81097e6fc09ccebf31138b06e4d** through the owner's model/artifact process. The service uses its directory-local .cache/huggingface and can attempt network retrieval if files are missing and offline mode is absent. Do not train, export, switch checkpoint or silently select legacy ONNX. A clean clone alone does not include the 842,609,220-byte weights; archive provenance and cache layout securely. Offline startup cannot succeed with an incomplete cache.

Ollama must be installed independently and contain llama3.2:latest. Check ollama list; acquisition of missing models is a separate owner decision, not an automatic setup step here. No cloud judge/embedding model is needed for normal catalog search.

## Configuration reference

Settings loads backend/.env by absolute file location; environment variables override file/defaults; unknown file settings are ignored. Default secret values are deliberately not reproduced.

| Variable | Purpose | Required / default behavior | Safe example |
|---|---|---|---|
| HOST | backend run.py interface | optional, 127.0.0.1 | 127.0.0.1 |
| PORT | backend run.py port | optional, 8000 | 8000 |
| APP_NAME | API title/health/log startup | optional, ShopAI Backend | ShopAI Backend |
| ENVIRONMENT | descriptive setting | optional, development; no production security switch implemented | development |
| POSTGRES_USER | database role | needed unless DATABASE_URL overrides; default role exists in code | shopai_app |
| POSTGRES_PASSWORD | database secret | configure privately; insecure default exists in code | &lt;set privately&gt; |
| POSTGRES_HOST | primary database host | optional, localhost | localhost |
| POSTGRES_PORT | primary database port | optional, 5432 | 5432 |
| POSTGRES_DB | primary database name | optional, shopai | shopai |
| DATABASE_URL | overrides PostgreSQL pieces | optional; postgres:// and postgresql:// converted to psycopg dialect | &lt;approved secret connection URI&gt; |
| TESTING_MODE | chooses in-memory SQLite configuration | optional false; test suites also patch settings/own fixture engines | false |
| DATASET_PATH | ingestion/fixture source; fallback directory base | optional absolute root/data/poorvika_products.jsonl default | ../data/poorvika_products.jsonl from backend cwd |
| LAYA_DECIDE_URL | decision client endpoint | optional, http://127.0.0.1:5056/decide; usable V2 mandatory for chat | http://127.0.0.1:5056/decide |
| OLLAMA_API_URL | generation/suggestions endpoint | optional, http://localhost:11434/api/chat | http://localhost:11434/api/chat |
| OLLAMA_MODEL | generation model | optional, llama3.2:latest | llama3.2:latest |
| OLLAMA_API_KEY | optional bearer token | default empty; used by suggestions and legacy LLMService; normal OllamaService.generate does **not** attach it | &lt;set privately if required&gt; |
| VITE_API_BASE_URL | browser backend base URL | required by frontend request helper; absent value throws | http://localhost:8000 |

Frontend VITE_* values are public browser configuration; never put secrets there. V2's port/model/revision are code constants, not these backend settings.

| Additional variable | Actual scope |
|---|---|
| HF_HOME | V2 service/run_benchmark overwrites it to directory-local cache |
| HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE | library offline controls; set 1 when starting an already provisioned cache |
| PORT | legacy Node server or switchable process, separate terminal scope; default 5055 / 5056 respectively |
| LAYA_MODEL | historical switchable ONNX selector base/specialist; not active Python V2 configuration |
| RAGAS_OLLAMA_MODEL | evaluator only, default gpt-oss:20b-cloud |
| RAGAS_OLLAMA_BASE_URL | evaluator judge, default https://ollama.com/v1 |
| RAGAS_OLLAMA_EMBEDDING_MODEL | evaluator only, default nomic-embed-text |
| RAGAS_OLLAMA_EMBEDDING_BASE_URL | evaluator embeddings, default http://localhost:11434/v1 |
| PYTHONIOENCODING | optional console UTF-8 diagnostics, not application setting |

Evaluator imports dotenv privately from backend configuration; OLLAMA_API_KEY is required for its cloud judge. Other available Ollama models are not proof they participate in normal chat.

## Database creation/import

Repository defines one products table using SQLAlchemy; no migration tool/history or relational order/user/cart tables. Database administrator must provision the chosen database/role with appropriate privileges. Example after role provisioning:

```powershell
createdb -h localhost -p 5432 -U shopai_app shopai
```

This database-creation command is **derived and not executed here**; local PostgreSQL tools may need PATH configuration. Do not run it against an existing database expecting idempotence. Store credentials privately, use least privilege and back up the target before ingestion.

From repository root, the standalone importer explicitly resolves its supplied catalog path:

```powershell
& ./.venv/Scripts/python.exe ./backend/scripts/import_products.py ./data/poorvika_products.jsonl
```

Importer creates tables and upserts by product ID, commits writes and reports imported/updated/skipped/errors. It is not a dry run or migration, and its printed summary—not exit code alone—must be checked. Alternate implementation from backend cwd is python -m app.database.ingest; the unauthenticated POST /api/products/ingest calls that implementation. The loaders differ in price cleanup/error handling. No source deletions are propagated as a catalog deletion. Verify health count, representative product details and stock before enabling shopping.

Normal backend lifespan checks a nonempty table; it imports only if count==0. If the PostgreSQL products table is missing, the count check catches an exception and logs a note rather than automatically creating the table. Use the explicit importer for a clean database. Primary connection failure can initialize persistent SQLite next to DATASET_PATH; inspect health.type and do not mistake fallback for successful PostgreSQL provisioning. ingest.py binds imported engine/session references, whereas session.py can later replace globals; fallback/ingestion combinations deserve review.

## Service startup — separate terminals

Run from repository root unless stated. These commands are derived from existing entry points; the current services were reused rather than freshly started in this handover.

**V2, existing approved cache, 127.0.0.1:5056:**

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
& ./laya_v2_service/.venv/Scripts/python.exe -u ./laya_v2_service/service.py
```

Keep one instance. Loading failure exits; inference is serialized. No configurable V2 bind/port CLI exists.

**Ollama, default 11434:**

```powershell
ollama list
ollama serve
```

Use the running Ollama service if already present. Do not launch a competing listener. Current normal configured model remains llama3.2:latest.

**FastAPI, normally 127.0.0.1:8000:**

```powershell
Set-Location backend
& ../.venv/Scripts/python.exe run.py
```

run.py uses settings.HOST/PORT with development reload and normal lifespan. To inspect an already initialized catalog without startup ingestion:

```powershell
Set-Location backend
& ../.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --lifespan off
```

lifespan off does not stop fallback initialization inside get_db if primary fails. Bind/reload/lifespan flags describe a local verification process, not production deployment.

**Frontend, 8080 explicitly:**

```powershell
Set-Location frontend
npm.cmd run dev -- --host 127.0.0.1 --port 8080 --strictPort
```

Set its .env base to http://localhost:8000 or matching loopback endpoint; restart Vite after configuration changes. This is a TanStack Start app with SSR/server entry, not a bare index.html-only SPA. Build: npm.cmd run build. Preview: npm.cmd run preview (script exists; serving a built production target was not verified here).

**Historical legacy Node, optional separate investigation only:**

```powershell
Set-Location laya_service
npm.cmd ci
npm.cmd start
```

This uses default 5055 and can download/load ONNX or emit a keyword fallback. It cannot satisfy the current backend V2 model guard. Never treat health.status=ok as model provenance.

switchable_server.mjs defaults 5056 and needs an ignored specialist integration module/bundle. Old SPECIALIST.md describes a historical setup, not current backend compatibility. Do not use it for current startup.

## Health and smoke procedures

```powershell
Invoke-RestMethod http://127.0.0.1:5056/health
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod 'http://127.0.0.1:8000/api/products?limit=1'
$payload = @{ message = 'Show me Sony earphones under 1000 rupees' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/chat -ContentType 'application/json' -Body $payload
```

V2 health should attest the pinned model/revision/loaded state; backend health should explicitly say PostgreSQL and expected catalog count. Frontend HTTP 200 verifies serving, not UI behavior. Also check the short protector query returns M.A/₹999/Out of Stock and add-to-cart gives a refusal without marker. Current fresh health and API smoke outputs are in [evidence](handover_evidence_2026-10-10/smoke.json).

## Diagnostics and troubleshooting

| Symptom | Inspect / action |
|---|---|
| Empty API base URL | frontend/.env VITE_API_BASE_URL; restart Vite |
| Unexpected Laya identity / unavailable text | verify 5056 /health, questions file and V2 model; do not redirect to 5055 |
| Port already in use | identify owning local process; use it or coordinate shutdown; do not kill unrelated services |
| PostgreSQL unavailable but app healthy | health.database.type may be SQLite fallback; fix primary and restart deliberately to leave fallback |
| Empty/missing catalog table | configured dataset path/cwd, explicit importer summary, DB role/table permissions |
| False empty accessory search | device vs manufacturer filters, retained model text, real category and SQL row count; see investigations |
| Sony budget returns nothing | inspect currency removal and category Headphones; preserve all-term logic |
| Suggestions hidden | valid page context, 503/422 response, model output validation; retry disabled and context cached |
| Slow unrelated requests | model queue and shared worker pool; synchronous ORM/event loop; benchmark realistic concurrency |
| Incorrect generated prose | compare supplied flattened_specs to output; prompts are not correctness guarantees |
| Garbled rupee logs | console UTF-8; avoid using encoding change to hide failing checks |

Backend logs record [AI FLOW], [TIMING] and extracted filters. Laya/Ollama HTTP timeouts are 60/120 seconds; requests timeouts are not a full multi-stage deadline. Normal frontend fetch has no explicit timeout; listing/details support abort signals. Suggestion timing diagnostics are opt-in via sessionStorage.setItem("shopai:suggestion-diagnostics","1"); logs/custom event show context-ready/request/received/visible timestamps. Successful suggestion questions use shopai:llm-suggestions:v1:<context key> sessionStorage, plus infinite React Query stale/retention; refresh reuses valid tab cache, content/model changes do not automatically invalidate its key. Popup dismissal is component-memory per context.

## Production/deployment status

No Dockerfile, compose file, migration system, CI workflow, committed Wrangler manifest, release pipeline, production host or backend process-manager configuration was found in the inspected source inventory. Lovable Vite config includes Nitro and a default Cloudflare build target; src/server.ts and src/start.ts implement SSR/error/CSRF wrappers. A passing build is not a verified deployed application.

Source-derived backend serving command without reload is uvicorn app.main:app with chosen host/port; production use additionally requires an owner-approved TLS/reverse proxy, authentication and protected ingestion, input/rate limits, secret injection, monitored processes, database backups, model artifact provisioning and validated CORS. This is a requirements list, not an implemented deploy procedure. No hosting credentials or deployment step is fabricated.

CORS currently allows localhost and 127.0.0.1 ports 8080/3000/5173 and http://192.168.56.1:8080, with credentials/methods/headers allowed. It is hardcoded and not an authentication control. Frontend server-function CSRF middleware does not secure the separate FastAPI APIs.

## Maintenance

Keep current checkpoint/provider until separately reviewed. Back up PostgreSQL and archive external model/ignored benchmark artifacts with hashes. Use isolated output directories for benchmarks and review logs for user text/exception/config leakage before sharing. Re-run relevant tests and manually validate browser/cart state when tooling is connected. Do not treat UI checkout timer, shipping/warranty/security text or client cart totals as real order processing.

Sources: [config](../backend/app/config.py), [run](../backend/run.py), [sessions](../backend/app/database/session.py), [importer](../backend/scripts/import_products.py), [Vite](../frontend/vite.config.ts), [V2](../laya_v2_service/service.py), [evaluation](../evaluation/evaluate.py).
