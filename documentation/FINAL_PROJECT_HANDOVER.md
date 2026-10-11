# Poorvika ShopAI — final project handover

**Prepared:** 10 October 2026, Asia/Calcutta. **Repository snapshot:** main, HEAD **29d29eb**. Remote configured as https://github.com/cubeaisolutionstech/Chatbot-laya.git. This is a source-and-evidence handover, not a production-readiness certificate.

The earlier Sony/accessory fixes, suggestion feature and audit reports are now committed in this snapshot. Current local health confirms React serving on8080, FastAPI on8000 with PostgreSQL508 products, Python Laya V2 on5056, and reachable Ollama11434. Legacy5055 is unreachable. No application behavior, database contents, providers or models were changed in this documentation task. Existing reports and baselines remain preserved.

## Reading map

This document owns project scope, component responsibilities, data model, status and handover decisions. Supporting documents own detailed reference material to avoid duplication:

| Guide | Contents |
|---|---|
| [Architecture](ARCHITECTURE.md) | Actual component diagram, product-search sequence, cart/context boundaries |
| [API reference](API_REFERENCE.md) | Every application route, actual serializers, schemas and failures; decision service endpoints |
| [Deployment and operations](DEPLOYMENT_AND_OPERATIONS.md) | Windows clean-checkout setup, all settings, startup/health/import commands, troubleshooting and deployment gaps |
| [Testing and benchmarks](TESTING_AND_BENCHMARKS.md) | Fresh checks, mock/real distinction, all discovered summary cohorts, research integrity and execution commands |
| [Evidence directory](handover_evidence_2026-10-10/source_inventory.json) | Source inventory, installed versions, health, OpenAPI, catalog/schema, benchmark recount, validation logs |

## 1. Objective, scope and non-goals

Poorvika ShopAI provides an electronics catalog storefront and conversational assistance for catalog discovery, filtering, product details, recommendations and client cart operations. It is designed to ground product facts in retrieved database rows and use a typed decision model before choosing actions. Related questions help shoppers explore an existing product or listing context.

Current scope does not include a transactional checkout, payment gateway, order persistence, shipping integration, authenticated customer accounts, real retailer inventory synchronization, calibrated shopping accuracy certification, model training during operations or a verified production deployment. UI policy/security/delivery claims are static text and are not verified business commitments.

## 2. Feature implementation and evidence

| Feature | Implementation status | Evidence / practical boundary |
|---|---|---|
| Home/catalog/detail pages | Implemented | React Query catalog APIs; build passes, prior/current HTTP checks; actual layout/browser acceptance unverified |
| Catalog text/category/brand/price/stock/rating/discount filtering | Implemented | SQLAlchemy parameterized queries and APIs; search is substring/all-term, not embeddings |
| Catalog pagination | Implemented | 99 rows plus sentinel within limit100; source/type/build; no rendered pagination acceptance here |
| Six-action chat | Implemented with recovery rules | V2 call first, validated choice, then existing regex overrides; not model-only routing |
| Catalog search/details | Implemented | Deterministic database-backed Markdown, no generation on these normal paths |
| Recommendations | Implemented, limited | In-stock rows sorted by customer rating; no verified use-case performance ranking |
| Explicit/reference cart add/remove/increase/decrease/view | Implemented client cart flow | Database resolution/stock guards, marker execution, stale-state checks; no server order/cart table |
| Full history-aware conversation | Partial | Visible turns retained locally, recent IDs/cart transmitted; no full history sent to Laya/Ollama |
| Device/accessory manufacturer distinction | Implemented bounded policy | Explicit compatibility links and implicit brand/family/alphanumeric model; regression and live evidence |
| Proactive generated related questions | Implemented | Context cache, 3–4 validated questions, original chatbot click path; no DOM/browser certificate |
| General/product-context generation | Implemented | Configured llama3.2:latest, guarded prompts/fallback; prose can still infer unsupported facts |
| Escalation/uncertainty policy | Incomplete | needs_escalation/answer_confidence retained but not operationalized; LOW_CONFIDENCE unused |
| Catalog import | Implemented write path | Two ingestion implementations; not rerun on active DB here |
| PostgreSQL fallback | Implemented | Persistent SQLite fallback, may import on connection failure; review operational consequences |
| Checkout/payment/orders | Simulated / absent | CartDrawer1200ms timer clears cart and shows success; no order/payment API |
| Wishlist/account/store controls | Partial UI placeholders | No supporting account/wishlist/order backend discovered |
| Legacy ONNX Laya | Historical separate service | Not current backend-compatible; server.js can fabricate keyword fallback |
| Specialist switchable ONNX | Experimental/historical | Requires ignored integration source/bundle; port5056 conflict and current guard mismatch |
| Python Laya V2 | Active locally; research provenance retained | Pinned model identity confirmed; production load/provisioning/calibration remain unresolved |
| JEV / Ragas / shopping evaluation | Standalone research tooling | Saved cohorts differ; not invoked by application requests |
| Deployment | Incomplete | Build works; no verified production host, CI, containers or release procedure |

## 3. Verified technology stack

Versions below are observed from local installed environments on this audit date, not just lower-bound dependency specifications. They do not prove fresh installation resolves identically.

| Layer | Observed version | Reproducibility source |
|---|---|---|
| Backend and V2 Python | 3.13.3 | [versions](handover_evidence_2026-10-10/versions.json) |
| Node | 22.14.0 | same evidence; lockfile contains Node22.13+ constraints |
| React | 19.3.0 | installed package; frontend manifest ^19.2.0 |
| Vite / TypeScript | 8.1.5 /5.9.3 | manifest pins Vite; npm lockfile |
| TanStack Start / Router / Query | 1.168.32 /1.170.18 /5.103.2 | installed packages/npm lock |
| Tailwind / Nitro | 4.3.3 /3.0.260603-beta | installed; Nitro default Cloudflare build target via Lovable config |
| FastAPI / Uvicorn | 0.142.2 /0.54.0 | backend lower-bound requirements; no backend lock |
| Pydantic / pydantic-settings | 2.13.5 /2.15.0 | same |
| SQLAlchemy / psycopg | 2.1.2 /3.3.6 | same |
| requests / httpx | 2.34.2 /0.28.1 | same |
| PostgreSQL server | 18.6 | fresh read-only SHOW server_version; not pinned as minimum |
| Python Laya / Torch / Transformers | 0.4.0 /2.14.1 /5.19.0 | isolated V2 metadata + requirements.lock.txt |
| datasets | 5.1.0 in V2 env | installed metadata/lock |
| Historical @receptron/laya | 0.1.2 installed | legacy package/lock; not active decision runtime |
| Generation | Ollama HTTP protocol, llama3.2:latest | safe configured-model verification + available model tags; Ollama daemon version not freshly measured |

Frontend additionally declares Radix/shadcn components, Streamdown and its code/math/Mermaid/CJK plugins, lucide, Sonner, Zod, React Hook Form, and AI UI helper dependencies. A declared package is not proof of an active AI provider. Active generation is the Python requests Ollama client; no OpenAI production client is called in the chat flow. Evaluator OpenAI-compatible judge and embedding clients are separate.

All dependency manifests/lockfiles are inventoried: backend/requirements.txt, frontend/package.json/package-lock.json/bun.lock, laya_service/package.json/package-lock.json, laya_v2_service/requirements.txt/requirements.lock.txt/laya_Model/requirements.txt, evaluation/requirements.txt, phase4_experiment/requirements.txt and scripts/requirements.txt. Script scraping requires requests/BeautifulSoup. Backend dependency ranges are broad; recording local versions is not a lockfile replacement.

## 4. Repository inventory and entry points

Generated environments, node_modules, cache/model binaries and build output are excluded from this narrative.

```text
poorvika-shopai/
├── README.md                       concise entry point
├── backend/
│   ├── run.py                      development Uvicorn launcher
│   ├── app/main.py                 FastAPI routers/CORS/lifespan
│   ├── app/config.py               Pydantic settings and DB URL
│   ├── app/database/               engine/session/fallback and JSONL ingestion
│   ├── app/models/product.py       products table + serializers
│   ├── app/routes/                 health/products/chat/suggestions
│   ├── app/schemas/                chat and suggestion contracts; unused product response declarations
│   ├── app/services/               ChatService, V2 adapter, Ollama and legacy LLM utility
│   ├── app/tools/                  ProductSearchTool
│   ├── scripts/                   standalone import and suggestion diagnostics
│   └── test_*.py                   backend/unit/integration/regression/concurrency
├── frontend/
│   ├── vite.config.ts              Lovable TanStack Start/Nitro config
│   ├── src/router.tsx              router/query client
│   ├── src/start.ts, server.ts      server middleware/SSR error handling
│   ├── src/routes/                 root/home/product list/detail
│   ├── src/components/storefront/  catalog/chat/cart/suggestions/navigation
│   ├── src/components/ai-elements/ conversation/input/message primitives
│   ├── src/components/ui/          shared UI primitives
│   ├── src/context/CartContext.tsx client state and persistence
│   ├── src/services/api.ts         API URLs/types/requests
│   ├── src/lib/                    cart commands/suggestions/timing/error helpers
│   └── tests/*.cjs                 helper/hook test harnesses
├── data/                           canonical/expanded JSONL, sitemap, tracked SQLite snapshot
├── scripts/                        two network catalog expansion/scraping tools
├── laya_service/                   legacy server and optional specialist wrapper
├── laya_v2_service/
│   ├── service.py                  active CPU/pinned HTTP decision service
│   ├── shopai_questions.json       six-action decision definitions
│   ├── laya_Model/                 supplied infer/evaluate/prepare/train scripts
│   └── results/                    tracked saved V2 evidence; cache excluded
├── evaluation/
│   ├── evaluate.py                Ragas capture/judge standalone
│   ├── benchmark_runner.py         labeled shopping pipeline evaluation
│   ├── jev_benchmark/              LocalLLaMA runner/metrics/dataset/experiments
│   └── results/                    mixed tracked summaries and ignored generated runs
├── benchmark_results/              historical September30 timing CSV
├── documentation/                  preserved audits/investigations and this handover
└── run_v2_jev.py                    HTTP V2 full benchmark to timestamped output
```

No Docker/compose, migration system or CI workflow was discovered. frontend/AGENTS.md says not to rewrite published Lovable history. Recent commits:29d29eb documentation/benchmark files,2b679a9 suggestions/chat improvements,fe36d13 benchmark ignores,6b731f7 specialist/ShopAI improvements. Initial worktree has untracked q; it was left untouched. Current handover updates do not commit or push.

The machine [source inventory](handover_evidence_2026-10-10/source_inventory.json) records file paths and inspection scope. Important authored modules/contracts were reviewed directly; UI primitives, lockfiles and historical logs were inventoried or inspected for relevant fields. This is not a guarantee of exhaustive semantic/security review of every binary, dependency or prior log line.

## 5. Architecture and frontend responsibilities

The [architecture diagrams](ARCHITECTURE.md) show the real current path:

**React → FastAPI → Python V2 → validated choice → existing guards → catalog/cart tool → deterministic reply or optional Ollama → frontend Markdown/cart helper.**

Frontend uses TanStack Start file routing and SSR wrappers, not a separate Express server. __root.tsx provides QueryClientProvider/CartProvider, navbar/footer, chat/cart drawer and toast UI. server.ts catches catastrophic SSR failures and dynamically resolves the TanStack server handler; start.ts adds error middleware and CSRF for server functions. That CSRF does not secure FastAPI.

Home requests first50 catalog items. Listing uses URL q/category/sort/page plus local maximum-price, brands, in-stock, rating and discount controls. ProductFilters/ProductGrid/ProductCard render actual fetched rows. Detail uses api.getProduct with a product-ID query key. Navbar/CategoryNav route TV & Audio correctly. SearchBar navigates to listing rather than calling a separate chatbot route. Listing next-page detection uses one sentinel row.

CartContext stores shopai_cart_items in localStorage and listens for storage events. It separates state/actions contexts and computes client totals. Initial restored JSON lacks complete item/quantity validation; storage-event handling checks array only. addToCart rejects explicitly unavailable products, while direct quantity update is not a database stock reservation and has no inventory-quantity cap. Browser UI state/multitab persistence are not certified here.

Chatbot lazily mounts ChatbotPanel. Panel holds visible messages/status/errors, recent product refs and current cart references. It sends message with a trailing client-context block. Streamdown renders replies. Product markers update recent IDs; cart helper executes validated markers and strips them. Full message history is not supplied to either model.

## 6. Backend responsibilities and orchestration

main.py mounts health/products/chat/suggestions routers and hardcoded development CORS, app version1.0.0. run.py launches reload-enabled Uvicorn using settings.HOST/PORT. Settings reads backend/.env and builds psycopg PostgreSQL URL, unless testing/direct override applies.

The chat route creates ChatService from a request-scoped SQLAlchemy Session and records pipeline timestamps in a finally block. LayaClient loads the shared questions file and calls V2 once with clean user message. Unsupported/malformed decisions return controlled guidance and stop processing; no current alternate-model fallback.

ChatService then applies existing conversational/details/cart/discovery/suggestion recovery patterns. This contradicts a model-only routing ideal even though Laya runs first. Filter extraction calls the static vocabulary utility from legacy LLMService; it does not make an additional generative extraction call. Bare catalog terms can also recover search after a model general/purchase decision.

product_search and recommendation retrieve catalog rows once through _find_products. Search returns a formatted table, recommendations restrict in-stock and sort rating; details resolve named/referenced rows and format up to eight specs. Add resolves database row, rejects unavailable stock, emits a client command for an available row. Cart view computes from supplied client context; mutation resolution checks catalog and membership before issuing a one-step command.

Informational product-page suggestion clicks can use selected-product flattened_specs with general generation after the Laya call. Other general acknowledgments are deterministic; remaining general queries use Ollama. Prompts cannot guarantee factual correctness. Successful generation is not independently checked against catalog claims after output. Existing static policy claims likewise need retailer verification.

Blocking model HTTP calls are offloaded to the worker pool. ORM still runs synchronously in async orchestration; concurrency tests prove yielding of model calls, not full production throughput or Session safety under arbitrary concurrent access.

## 7. Database architecture and catalog

Fresh read-only metadata confirms PostgreSQL18.6, public table products. There are **no modeled table relationships**, order/user/cart tables or Alembic migrations. Declarative Base plus create_all handles missing tables during explicit ingestion; it does not migrate existing schema changes.

| Column group | Actual model columns/types |
|---|---|
| Identity | id VARCHAR150 primary key; name VARCHAR255/brand VARCHAR100/category VARCHAR100 nonnull; model VARCHAR150; sku VARCHAR100 nullable unique; item_code/erp_item_code VARCHAR50 |
| Money | price/online_price nonnull Float; mrp/shop_price/discount_percent Float; currency VARCHAR10 |
| Availability | in_stock Boolean; stock Integer; availability VARCHAR100 nonnull |
| Reviews | rating Float; rating_count Integer |
| Content | image/description/url/canonical_url Text; images JSON |
| Specs/provenance | specifications/flattened_specs JSON; source_hash VARCHAR100; scraped_at VARCHAR50 |

Indices are declared on ID/name/brand/category/SKU/price/discount/in_stock/stock/rating; no text-vector/composite-query index or foreign key is declared. Prices use Float, not Decimal; client/rendered INR amounts are display values, not authoritative checkout amounts. JSON columns are **JSON**, despite importer comments referring to JSONB. scraped_at is a string, not a DateTime column.

Both canonical and expanded JSONL currently contain508 records, zero duplicate IDs in fresh parsing, each3,478,197 bytes. Fields: url, canonical_url, name, brand, model, sku, product_id, item_code, erp_item_code, online_price, mrp, shop_price, currency, availability, stock, rating, rating_count, description, images, specifications, source_hash, scraped_at. Raw specs use attributeGroups/attributes and highlights; ingestion flattens name/value pairs, normalizes mobile Generic Name to Mobiles and defaults missing category to Electronics. Stock>0 determines in_stock; availability URI may preserve the source value independently. Discount derives from MRP versus online_price. Primary image is first images entry, with legacy image fallback.

Two import paths exist: app/database/ingest.py and backend/scripts/import_products.py, with different price cleanup/error treatment. Both upsert ID; neither deletes products missing from an input catalog. Network scrapers write expanded JSONL and are not automatic freshness synchronization. Their execution can replace output files and should be reviewed separately.

ProductSearchTool ANDs metadata constraints and meaningful text terms, with OR across each term's fields. Category mapping includes parent UI groups and child aliases (e.g. earphones→Headphones; TV & Audio→Television/Headphones/Speakers; accessories includes Temper glass). Brand uses the actual stored manufacturer predicate. Exact name is an alternate text condition under the same attribute predicates, with default ordering preference. Short model retention on accessory path prevents S7 omission; compatibility device brands are not mistaken for manufacturers in documented forms. This is bounded strict text matching, not proof of physical compatibility.

session.py checks PostgreSQL with connection cache and can switch to persistent SQLite beside dataset path, initialize its table and ingest if empty. Fallback remains active until process restart. Timing names postgres_query_* can then refer to SQLite. Missing PostgreSQL tables are not automatically recovered by startup count verification; see [operations](DEPLOYMENT_AND_OPERATIONS.md).

## 8. Laya service identities and confidence

| Service | Role/model loading | Current status / caution |
|---|---|---|
| laya_service/server.js | @receptron/laya default Laya.load() ONNX; historical base convaiinnovations/laya; default5055 | unreachable locally; fabricated keyword fallback exists; not backend-compatible V2 |
| laya_service/switchable_server.mjs | ignored specialist integration start(); LAYA_MODEL=base/specialist; default5056 | historical opt-in; missing clean-clone dependency; port conflict with V2 |
| laya_v2_service/service.py | laya.load(Mass121/laya-typed-decisions-v2, pinned revision, device=cpu), once | active5056, no model fallback; inference lock |

V2 binds loopback only after successful load. Request is state plus nonempty typed questions; response exposes raw/answers/choices/shopai and identity. Source points to https://huggingface.co/Mass121/laya-typed-decisions-v2, with pinned revision6fb41711ea5ff81097e6fc09ccebf31138b06e4d. Supplied infer/prepare/train/evaluate sources remain experimental/research utilities. Their presence does not mean training ran here. The older V2 README describes phase-one isolation/no integration; that is **historical and now stale** relative to current client/defaults.

Backend accepts only product_search, product_details, recommendation, add_to_cart, cart_action, general_query and validates genuine scores without renormalizing/inventing them. Choice confidence is normalized-entropy-derived; answer_confidence is a separate temperature-scaled answer confidence. Noul confidence follows binary max probability semantics. None should be treated as guaranteed correctness. Adapter checks model ID but not revision, and needs_escalation/action are not execution policies. Full contract and error codes are in [API](API_REFERENCE.md).

## 9. Generative integration and suggestion lifecycle

Active OllamaService defaults to local http://localhost:11434/api/chat, model llama3.2:latest; safe current-model verification confirms it. Persistent requests Session, nonstreaming requests, keep_alive10m. Normal generation uses compact catalog context and low temperature; informational questions receive flattened specifications. On error, catalog formatting is retained if products exist, otherwise controlled guidance. Legacy LLMService's network extraction methods exist but are not active production decision routing; only its static filter/format helpers are reused.

Suggestions directly call Ollama, not Laya, to produce validated3–4 questions. Context comes from cached product details or listing q/category. ProductSuggestionPopup uses infinite query staleness/retention, no retries/focus/reconnect refetch, successful per-tab sessionStorage caching and per-context in-memory dismissal. It hides when main chat is open, failed or lacks meaningful context. There is no arbitrary fixed timeout before popup; availability depends on generation/cache and rendering. Selecting dismisses, opens the original panel and sends once, optionally with suggestion_product_id. Existing product data is reused; no extra product-fetch loop for popup generation.

Suggestion input is bounded by Pydantic; output is unique normalized question strings, no canned fallback. Server-Timing and opt-in frontend timestamps measure stages. Cached questions may outlive catalog/model/context changes because keying is product ID or query/category, not content revision.

## 10. Setup, APIs, tests and benchmark evidence

All Windows commands and variables are centralized in [operations](DEPLOYMENT_AND_OPERATIONS.md); every verified route/wire shape in [API](API_REFERENCE.md); methodology/cohorts in [testing](TESTING_AND_BENCHMARKS.md).

Fresh handover checks: **138 backend executions PASS,18 frontend helpers PASS,TypeScript/build exit0**, real service health and three real API smoke requests passed. Full JEV inference was **not rerun**; saved raw decisions freshly recount718/2000 base,1530/2000 ONNX specialist,1576/2000 Python V2. These are35.9%,76.5%,78.8% respectively, with different runtime/checkpoint experiments and meaningful latency/calibration tradeoffs. Full details and discrepancies stay separate in testing guide.

Historical sources preserved: [Oct7 technical audit](shopai_technical_audit_2026-10-07.md), [Oct9 stabilization](shopai_stabilization_audit_2026-10-09.md), [Sony](sony_search_investigation_2026-10-10.md), [explicit compatibility](accessory_compatibility_investigation_2026-10-10.md), [short query](short_accessory_investigation_2026-10-10.md). Their dates/branches/HEADs describe the earlier worktree, not current29d29eb.

## 11. Known issues, security and deployment limits

Priority unresolved work:

1. Decide model-only routing versus existing action overrides using labeled shopping cases; preserve rejection-only cart safeguards. Current real short-query model decision still needs recovery.
2. Define calibrated uncertainty/clarification/escalation policy from actual shopping evidence; enforce checkpoint provenance at integration boundary.
3. Validate typed cart/client context and persisted storage bounds; client totals and prices are untrusted. Direct cart quantities are not stock reservation.
4. Protect catalog ingestion and expensive model endpoints with appropriate auth/rate/input controls before public exposure. No current auth dependency.
5. Make simulated checkout's status truthful; no payment/order/delivery implementation exists.
6. Connect browser tooling for layout, mobile, keyboard, real cart/storage/multitab acceptance.
7. Test concurrency, queue/worker-pool pressure and synchronous ORM at realistic load. No production P95 claim.
8. Lock reproducible backend dependencies; resolve ignored specialist clean-clone dependencies only if that experiment is actually needed.
9. Review generated answers and static shipping/warranty/return/security promises against supplied catalog/retailer evidence.
10. Review privacy/log redaction: current logs can include user messages, raw exceptions, configured URLs and database connection errors.

Secret .env files and model/cache outputs are ignored; no tracked .env or safetensors/ONNX file was found in current tracked-file inventory. Config contains an insecure database credential default, deliberately withheld here. Ignoring files does not prove absence of secrets in Git history, binaries or logs. This handover checks newly written docs for secret patterns but does not certify an exhaustive historical secret audit.

Hardcoded CORS allows specific local origins and credentials; it is not auth. V2 loopback/default backend loopback reduce local exposure but do not provide a production security boundary. Suggestions trust caller context. No guaranteed prompt-injection resistance is demonstrated.

No committed Docker/compose/CI/migrations/deployment manifest or verified hosting procedure. Lovable/Nitro Cloudflare build integration exists; published backend/model infrastructure is not documented by source. Operations guide explicitly separates source-derived serving commands from missing production prerequisites.

## 12. GitHub policy and owner workflow

This task leaves documentation changes unstaged and uncommitted. Initial remote/branch/history were inspected locally; remote branch parity, permissions and GitHub deployment settings were not verified. Do not rewrite published Lovable history.

Already excluded by ignores: .env/private environment overrides, .venv, node_modules, Python/cache files, model/cache directories, generated frontend .output/.wrangler/dist, ignored JEV result directory, isolated specialist directory, selected generated evaluation/suggestion artifacts and accidental %SystemDrive% cache. Sanitized .env.example files are allowed.

**Actually tracked**: canonical/expanded catalog JSONL, sitemap, data/poorvika_fallback.sqlite3, official local JEV dataset/parquet, V2 result JSON/CSV/reports and historical documentation logs. Do not claim all data/results are ignored. The largest tracked files are listed in [artifact audit](handover_evidence_2026-10-10/tracked_large_files.json). Review data redistribution/provenance, SQLite snapshot and logs before future sharing. No existing artifacts were removed or baselines overwritten.

Suggested owner-only workflow after review, not executed here:

```powershell
git status --short
git diff --check
git diff -- README.md documentation/FINAL_PROJECT_HANDOVER.md documentation/ARCHITECTURE.md documentation/API_REFERENCE.md documentation/TESTING_AND_BENCHMARKS.md documentation/DEPLOYMENT_AND_OPERATIONS.md
git switch -c docs/final-handover
git add README.md documentation/FINAL_PROJECT_HANDOVER.md documentation/ARCHITECTURE.md documentation/API_REFERENCE.md documentation/TESTING_AND_BENCHMARKS.md documentation/DEPLOYMENT_AND_OPERATIONS.md
# Review and selectively add handover evidence after checking privacy and size.
git diff --cached --check
git diff --cached --stat
git commit -m "docs: add evidence-based ShopAI handover"
git push -u origin docs/final-handover
git log -1 --oneline
git status --short
```

Do not blindly add the whole worktree or untracked q. Owner should compare remote refs/PR checks separately; no successful push is claimed.

## 13. Handover checklist and maintenance

- [x] Source, manifests, safe examples, routes, Git state/history and historical reports inspected.
- [x] Active runtime identified; V2 and legacy distinguished.
- [x] APIs/schema/environment/startup derivation documented.
- [x] Fresh regression/type/build checks and read-only service/database evidence captured.
- [x] Saved benchmark counts, failure coverage and conflicting labels separately documented.
- [x] Main/supporting guides and root README prepared.
- [ ] Clean-clone installation/provisioning proved on a second machine.
- [ ] Browser acceptance and real cart persistence proved.
- [ ] Production security/checkout boundaries resolved.
- [ ] Model uncertainty/action recovery policy approved and labeled.
- [ ] Load/queue profiles and target deployment established.
- [ ] Owner reviews artifact privacy/licensing and selects final Git changes.
- [ ] Lead accepts unresolved items and assigns owners/dates.

Owner maintenance: keep catalog imports explicit/backed up, inspect health database.type, preserve checkpoint/questions/metrics provenance, run targeted regressions after source changes, archive model and ignored benchmark artifacts outside Git, and revalidate UI once browser tooling is available. Obtain actual retailer fulfillment/policy truth from the business rather than inferring it from demo text.

Missing handover inputs: production host/URLs, secret delivery process, approved CI/release ownership, model artifact distribution policy, business checkout/payment scope, browser acceptance environment, performance targets, retailer data refresh/license policy, calibrated shopping evaluation dataset and escalation owner.

## 14. Glossary

| Term | Meaning here |
|---|---|
| ShopAI | Storefront plus catalog-grounded shopping chatbot |
| Laya/System-1 | Typed decision engine; not final response generator |
| V2 | Active Mass121 Python checkpoint/service, distinct from ONNX specialist |
| ONNX specialist | Historical exported convaiinnovations/laya-typed-decisions experiment |
| choice / score / noul | Categorical / ordinal score / binary typed decision heads |
| confidence | Genuine model field; entropy-derived for choice, not invented certainty |
| answer_confidence | Separate answer-confidence metadata retained by adapter |
| JEV | Repository shorthand for LocalLLaMA typed-decisions evaluation |
| Ragas | Standalone response-quality evaluator; coverage may be only a subset |
| exact_name | Internal alternate catalog text equality under common filters |
| shopai_client_context | Trailing JSON convention inside chat message |
| SHOPAI_* markers | Server-to-client selection/cart command conventions |
| SQLite fallback | Persistent local catalog activated after primary failure |
| keep_alive | Ollama model retention request, not client response caching |
| Sentinel row | Extra listing row indicating next-page existence |

## 15. Source-of-truth references

| Claim area | Source |
|---|---|
| Routes/CORS/lifespan | [main.py](../backend/app/main.py), [routes](../backend/app/routes/products.py) and captured OpenAPI |
| Settings | [config.py](../backend/app/config.py), safe backend/frontend .env.example |
| Catalog model/import | [product.py](../backend/app/models/product.py), [ingest.py](../backend/app/database/ingest.py), [import_products.py](../backend/scripts/import_products.py) |
| Database fallback | [session.py](../backend/app/database/session.py) |
| Chat/filters/cart/format | [chat_service.py](../backend/app/services/chat_service.py), [product_search_tool.py](../backend/app/tools/product_search_tool.py) |
| Decision/generation | [laya_client.py](../backend/app/services/laya_client.py), [ollama_service.py](../backend/app/services/ollama_service.py) |
| Active V2 | [service.py](../laya_v2_service/service.py), [questions](../laya_v2_service/shopai_questions.json) |
| Frontend routing/API/cart | [router](../frontend/src/router.tsx), [API](../frontend/src/services/api.ts), [CartContext](../frontend/src/context/CartContext.tsx), [helper](../frontend/src/lib/chat-cart.ts) |
| Suggestion timing/click/cache | [popup](../frontend/src/components/storefront/ProductSuggestionPopup.tsx), [helper](../frontend/src/lib/product-suggestions.ts), [ChatbotPanel](../frontend/src/components/storefront/ChatbotPanel.tsx) |
| Checkout boundary | [CartDrawer](../frontend/src/components/storefront/CartDrawer.tsx) |
| Build/SSR | [vite config](../frontend/vite.config.ts), [server](../frontend/src/server.ts), [start](../frontend/src/start.ts) |
| Tests/research | [testing guide](TESTING_AND_BENCHMARKS.md), linked runners and evidence registry |

## 16. Final documentation audit and change manifest

Created FINAL_PROJECT_HANDOVER.md, ARCHITECTURE.md, API_REFERENCE.md, TESTING_AND_BENCHMARKS.md and DEPLOYMENT_AND_OPERATIONS.md under documentation; updated root README.md. New handover_evidence_2026-10-10 contains the reproducible documentation checker and source/runtime/QA/benchmark/Git evidence; [exact evidence manifest](handover_evidence_2026-10-10/manifest.json) lists every new artifact.

Existing tracked documentation/accessory_compatibility_2026-10-10/laya_restart.log and documentation/short_accessory_2026-10-10/api_runtime.log naturally appended output while the already running services handled tests and smoke requests. They were not rewritten or reset. Application source, catalogs, benchmark baselines and prior reports are unchanged. Untracked q remains untouched. The staged diff is empty; no Git mutation/commit/push occurred.

New authored Markdown checks pass. Repository-wide git diff --check exits **2** because appended Windows CRLF lines in the old Laya runtime log are reported as trailing whitespace. This failure is preserved in the evidence, not mislabeled as a passing check. The README-only Git check and standalone checks of all new guides are reported separately. Diagram structure is documented; graphical Mermaid/browser rendering was not verified.
