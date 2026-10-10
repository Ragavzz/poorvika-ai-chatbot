# Poorvika ShopAI — audit and stabilization

9 October 2026, Asia/Calcutta. Local workspace audit; no commit, push, model download/training, provider switch, database replacement or production restart. Existing uncommitted work was preserved.

## Outcome and limits

The current local application uses **Mass121/laya-typed-decisions-v2**, Python CPU, on **127.0.0.1:5056**, pinned revision **6fb41711ea5ff81097e6fc09ccebf31138b06e4d**. Live health confirms identity and loaded status. backend/.env already pointed to V2; configuration defaults, environment example and root startup instructions were stale. Old port 5055 was unreachable.

Targeted fixes validate genuine decision probabilities/confidence, retain separate answer_confidence, correct the failure message, align default/example/runbook with the existing V2 configuration, restore pagination and TV navigation, and move blocking Laya/Ollama calls off the async event loop. No model or dependency was changed.

**The project is not certified fully production-ready.** Existing regex action overrides remain after the Laya call and conflict with the model-only routing requirement. Removing them wholesale would change established safety/suggestion behavior covered by existing tests. The smallest alternative is proposed below. Uncertainty/escalation policy, malformed cart context, simulated checkout and browser acceptance remain unresolved.

## Architecture and request flow

~~~mermaid
flowchart LR
 A[React chatbot] --> B[FastAPI /api/chat]
 B --> C[Python V2 /decide]
 C --> D[Validated typed choice]
 D --> E[Existing action overrides]
 E --> F[SQLAlchemy product tool]
 F --> G[PostgreSQL]
 G --> H[Deterministic catalog reply]
 E --> I[Optional Ollama]
 H --> J[Markdown and cart markers]
 I --> J
~~~

Frontend: React 19, TypeScript, Vite 8, TanStack Start/Router/Query, Tailwind 4, Radix/shadcn components, Streamdown, lucide and Sonner. QueryClient default stale time is 30 seconds, retention five minutes, focus refetch disabled. Chat panel is lazy-loaded. Cart state uses React Context/localStorage.

Backend: FastAPI/Uvicorn, Pydantic 2/settings, SQLAlchemy 2, psycopg 3 and requests. Dependency manifests mostly use minimum versions; they do not alone prove installed versions. Python V2 uses a separate environment, persistent CPU checkpoint, standard-library HTTP server and a prediction lock. Historical service README records Python 3.13 and Laya 0.4.0; live health does not independently attest executable/dependency versions or weight bytes.

PostgreSQL is active. Existing session.py can activate persistent SQLite fallback when PostgreSQL fails; preserved, not introduced here. Timing fields named postgres_query_* may then describe SQLite. Laya never accesses PostgreSQL and does not generate final shopping prose.

## Frontend components and context

Chatbot.tsx opens ChatbotPanel.tsx. The panel maintains visible messages, loading/error state, recent product IDs and current cart references. api.ts calls configured VITE_API_BASE_URL + /api/chat using JSON **{message: string}**. Backend returns **{response: string}**. Empty base URL is rejected by the API client.

The wire message appends a shopai_client_context JSON block containing recent_product_ids, cart and optional suggestion_product_id. Backend strips this before Laya: **Laya receives only state.message**, not complete history/cart. Visible conversation history is retained in React, but full previous turns are not sent to either model.

MessageResponse uses Streamdown for Markdown. SHOPAI_PRODUCTS markers update recent selection. chat-cart.ts executes SHOPAI_ADD_TO_CART and SHOPAI_CART_ACTION markers and strips them before rendering. Addition independently fetches catalog product data and checks stock. Other mutations validate membership, expected client quantity and exact one-step target. Helper tests cover failed lookup, out-of-stock, stale state, invalid quantities and conflicting instructions. Marker issuance alone does not prove a real browser cart changed.

CartContext stores shopai_cart_items and listens for storage events. Restored JSON does not receive full item/quantity validation. Client prices/totals are not authoritative checkout amounts. ProductCard/ProductDetails use catalog facts. Listing/detail routes fetch via React Query. Navbar/CategoryNav/SearchBar provide navigation; SiteFooter includes static policy promises not verified from retailer policy. Wishlist/account/store links include unimplemented controls.

ProductSuggestionPopup observes existing product cache, asks /api/chat/suggestions for three or four model-generated questions, caches valid output in React Query/sessionStorage, avoids retries and hides failed output. Clicking opens the original chat and submits once with product context. A live request returned four questions; helper/hook harness tests passed. These do not establish actual DOM layout, accessibility, browser refresh or multitab persistence.

## Backend behavior and API routes

GET /, /api/health, /api/products, /api/products/search, /api/products/{id}, /api/categories, /api/brands. POST /api/chat, /api/chat/suggestions and /api/products/ingest. Ingestion was not executed.

ChatService calls Laya once, validates its result, then applies pre-existing recovery/disambiguation regexes. Filter extraction uses existing vocabulary/rules after action selection; separate recovery rules also override the selected action.

Actual accepted choices: **product_search, product_details, recommendation, add_to_cart, cart_action, general_query**. Product search uses parameterized ORM filters, category synonyms, price/brand/stock/rating/discount constraints, AND across meaningful terms, stable sorting and limit <=100. Model-name position ranking prefers names over accessory description mentions.

Search/details/recommendations format actual retrieved rows deterministically. Recommendations rank in-stock candidates by rating and disclaim absent verified use-case performance. Add-to-cart resolves a database row, checks stock, then emits a client command. Cart view uses supplied client context; mutation resolution checks catalog and membership. General acknowledgments are deterministic; other general/product-page information can use Ollama.

Configured generation remains **llama3.2:latest**. Shared requests Sessions and keep_alive=10m already existed. Suggestions use structured schema output. Product contexts are compact and grounded, but prompts cannot guarantee hallucination-free prose. Historical suggestion-click output asserted manufacturer gaming benefits without demonstrated supplied evidence. Generation failure falls back to catalog formatting when products exist, otherwise returns a controlled error.

## V2 contract and confidence semantics

Request: state object plus nonempty questions object; intent defines six choice criteria, needs_escalation defines noul. Response includes model, revision, latency_ms, raw, answers, choices and optional shopai. Backend consumes answers.intent. Service loads the pinned checkpoint once, has no model fallback, returns 400 for invalid input and 500 for inference errors. Service latency includes inference-lock waiting, excludes HTTP transport/startup.

Adapter now rejects non-object output/answers/intent, unexpected model, unsupported action, missing/nonfinite/out-of-range confidence, wrong probability keys/values and distributions outside a 0.001 sum tolerance (four-decimal rounding). It does not invent/renormalize probabilities. Optional answer_confidence and action metadata are retained separately. Backend does not enforce revision and does not act on escalation/action metadata.

Installed laya/agent.py documents choice/score **confidence as normalized entropy**, while **answer_confidence** is temperature-scaled answer confidence with optional binning. Noul confidence is max(p,1-p). They are not interchangeable correctness guarantees. Live search had confidence 0.96 versus answer_confidence 0.9885. Existing LOW_CONFIDENCE=0.15 is unused; no calibrated clarification threshold exists.

Old laya_service/server.js uses @receptron/laya ONNX and can fabricate fixed-confidence keyword-router outputs on failure. It is inactive locally and fails the V2 model guard. switchable_server.mjs is another ONNX entry point defaulting to 5056, so must not compete with V2. The ONNX specialist and Python V2 are separate configurations/checkpoints.

## Benchmark comparison

Sources: [B](../evaluation/jev_benchmark/results/baseline_v2_20261004_summary.json), [S](../evaluation/laya_specialist_onnx_isolated/benchmark/runs/20261005_184532_IST/specialist_summary.json), [V](../laya_v2_service/results/jev_full_20261008T115135_157161Z/laya_jev_benchmark_summary.json). Counts were freshly recounted from B/S raw JSONL and V decision JSON. Metrics below are historical artifacts, not newly run inference benchmarks.

| Area | Base B | ONNX specialist S | Python V2 V |
|---|---|---|---|
| Model | convaiinnovations/laya | convaiinnovations/laya-typed-decisions | Mass121/laya-typed-decisions-v2 |
| Runtime | @receptron/laya 0.1.2 ONNX | Same Node runtime, FP32 ONNX CPU | Python Laya CPU |
| Revision | Immutable revision NOT VERIFIED | 1a793eb568e6718f15941d08f85432581df534e3 | 6fb41711ea5ff81097e6fc09ccebf31138b06e4d |
| Correct/expected | 718/2000 | 1530/2000 | 1576/2000 |
| Overall accuracy ↑ | 35.90% | 76.50% | 78.80% |
| Choice accuracy ↑ | 28.8333% | 73.1667% | 75.50% |
| Score accuracy ↑ | 31.75% | 72.25% | 75.25% |
| Noul accuracy ↑ | 48.50% | 85.50% | 86.83% rounded |
| Score MAE ↓ | 0.690507 | 0.247058 | 0.2475 |
| Soft-gold Brier ↓ | 0.100405 | 0.018859 | 0.0269 |
| Repository ECE ↓ | 0.153419 | 0.417561 | 0.1312 |
| Mean case HTTP ms | 8847.84 | 11641.46 | 7874.12 |
| P50 ms | 9590.26 | 12517.73 | 8542.74 |
| P95 ms | 14133.02 | 18004.62 | 11390.68 |
| Maximum ms | 16615.78 | 34827.02 | 15556.53 from decision JSON |
| Successful/failed decisions | 2000/0 | 2000/0 | 2000/0 |
| Fallback | 0 recorded | 0 recorded | Service has no fallback; summary lacks per-request provenance |
| Local active | 5055 unreachable | Historical/opt-in | Healthy on 5056 |
| ShopAI impact | Historical routing errors | Generic accuracy gain; rules still needed | Current integration; shopping accuracy not quantified |

Base→specialist: **+40.60 percentage points, +812 correct, +113.09% relative accuracy**. Choice +44.3333 pp/+266; score +40.50 pp/+324; noul +37 pp/+222. MAE drops 0.443449 (~64.22%); Brier drops 0.081546 (~81.22%). ECE rises 0.264142 (~172.17%, worse). Mean case HTTP latency rises 2793.62 ms (~31.57%). **Accuracy improved, but inference-path HTTP latency increased.** These HTTP artifacts cannot isolate inference/network causal timing.

Specialist→V2: +2.30 pp/+46 correct; choice +2.3333 pp, score +3 pp, noul ~+1.3333 pp. Saved V2 latency is lower, while Brier and MAE are higher. Different runtime/checkpoint experiments are not a controlled production speed comparison. Entropy-based ECE should not be marketed as calibrated correctness probability.

S records weights SHA-256 4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e and ONNX SHA-256 e2b4eeeb1347a94680839a0bdcd473de53c151ab6134193c82ba525459c59474. V2 model_verification.json records weights SHA-256 c10b666f708e0e3dfbc6e512bfe4bae0340dcdac2ff167f38137c50e1089071d. Loaded bytes were not rehashed. Base/specialist evidence establishes a checkpoint/export change under the same runtime, not a newly invented architecture.

## Benchmark Validity / Reliability

Fresh dataset parsing: LocalLLaMA/typed-decisions test, 400 cases, 2000 decisions: 600 choice, 800 score, 600 noul. Four workflows. Dataset SHA-256 matches 46beeb91b458bc737baddb2fe333268bb038847eafc31e55e54aaf3e3553280b. B/S report sequential execution, zero retries, 60-second timeout and 400 successful cases. Fresh raw recount reproduced 718/1530 with no failed cases. Both zero-failure runs establish no reliability improvement.

Baseline runner reports strict correct/expected and successful-only accuracy. General runner metrics exclude errored rows from scoring cohorts. Failed-run results must disclose coverage. Earlier evaluation/jev_benchmark/results/laya_jev_benchmark_summary.json is a five-case V2 compatibility run with all 25 decisions failed: its zero Brier/ECE represents absent evidence, not perfect calibration. Compatibility note documents top-level answers repair. V full decision JSON has 400 cases, 2000 rows, 1576 correct and no errors.

V summary lacks full per-response model identity; attribution relies on run_v2_jev.py/endpoint and contemporaneous service evidence. baseline_v2_20261006_214159_summary.json labels base while reporting specialist metrics; summary builder hardcodes base identity. Do not treat labels as loaded-model proof. The October7 report flags attribution; that run's raw identity was not freshly audited today.

No full benchmark was rerun. Matched hardware load, statistical significance, training overlap and shopping generalization are NOT VERIFIED. V per-decision latency divides five-question case timing by five; it is not independently timed requests. Generic benchmark accuracy is not application/business accuracy.

## Database and latency

Fresh read-only PostgreSQL query: **508 products, 0 duplicate IDs, 0 duplicate names, 0 stock/in_stock inconsistencies**. Category counts include Mobiles 91, Television 56, Computers 49, Headphones 35, Smartwatches 36; full distribution is in fresh evidence JSON. products has string ID, name/brand/category/model/SKU, Float prices/MRP/discount, stock/availability, ratings, media/descriptions and JSON specs. Catalog consistency does not prove current retailer fulfillment.

Live sample HTTP timings before worker-pool patch: Sony search 7906 ms, selected details 18534 ms, thanks 3390 ms, okay 2237 ms, add marker 2402 ms, cart view 10383 ms. Single samples are not P50/P95. Fresh TestClient timing after patch: ~2542 ms Laya, ~10 ms isolated SQLite query, ~2555 ms total, no Ollama. This is not PostgreSQL production timing.

Concurrent live suggestions took 18283 ms round trip versus backend_api_ms 7892 and ollama_ms 7878. Pre-handler delay coincided with blocking chat inference. Source confirms synchronous requests in async orchestration. Worker-pool patch and two yielding tests address this; production speedup is NOT VERIFIED. V2 inference lock still serializes model work; ORM remains synchronous and shared Session concurrency needs load testing.

September30 laya_vs_bypass CSV is an older flow with generation on search and details misclassified as cart, not current V2 latency. Historical suggestion logs are not today's browser evidence. Cold/warm paired timings, queue profiles, resource use and deployed latency remain NOT VERIFIED.

## Changes and verification

- config.py and sanitized .env.example use intended V2 5056; private .env unchanged.
- laya_client.py validates typed probabilities/confidence and retains answer_confidence/action.
- chat_service.py gives a controlled configured-service error and offloads model HTTP calls to existing worker pool.
- products.index.tsx uses 99 displayed rows plus one sentinel within backend limit 100. Previously length>100 could never enable Next.
- CategoryNav.tsx/Navbar.tsx use TV & Audio for that label; API returns TVs/headphones/speakers.
- README distinguishes V2 and legacy ONNX; .gitignore allows sanitized examples and ignores generated .output/.wrangler.
- Added contract and coroutine responsiveness tests, no dependencies.

**Fresh checks:** 103 backend suite executions + 2 concurrency tests PASS; 18 frontend helper tests PASS; TypeScript and production build exit 0. Counts include inherited tests repeated by suggestion-click class, not 105 unique scenarios. Main eight tests mix isolated SQLite with real V2 calls; other regressions use model mocks.

Live health/catalog/search/details/acknowledgments/cart marker/cart view/suggestions checked. Unknown search returns [], missing product 404, invalid limit 422. Frontend HTTP 8080 returns 200. Browser unavailable: no connected surfaces and iab creation failed. Layout/mobile/real cart mutations/refresh/multitab/keyboard acceptance **NOT VERIFIED**. Ingestion/payment/delivery not executed.

Build warnings: large chunks, plugin overhead, ignored inlineDynamicImports and WASM fallback. Tests warn about existing testclient deprecation and unclosed SQLite resources. Do not add dependencies solely to silence warnings.

## Security and Git readiness

Credential fields/default DB credential: FOUND, values withheld. Tracked .env files: NOT FOUND. Common token/private-key patterns in tracked text: NOT FOUND by bounded scan. Full history/ignored/untracked/binary scan: NEEDS REVIEW, NOT VERIFIED.

No authentication dependency protects catalog ingestion. Chat/cart/context/storage lack complete typed bounds and malformed values can cause downstream errors. Client totals are untrusted for orders. Logs include user text/raw exceptions; production redaction requires review. CartDrawer checkout only waits 1200 ms, clears cart and claims order success: no order/payment backend. Static delivery/warranty/return/security claims are not verified. Preserved rather than redesigned.

Branch main, HEAD fe36d13. Initial worktree already had seven modified tracked files and substantial untracked suggestion/V2/docs work. Nothing reset/staged/committed/pushed. Benchmark/model artifacts remain ignored. Opt-in ONNX source depends on ignored evaluation code; fresh-clone provisioning needs review. V2 service/questions must be included in a future intended integration commit. Env example exception now allows sanitized setup files; inspect them before staging. Large model binaries stay external.

Recommended later commit separation after reviewing existing work:

1. fix: validate Laya V2 decisions and isolate blocking inference
2. fix: restore catalog pagination and TV navigation
3. docs: document current V2 startup and verified ShopAI audit
4. Review existing suggestion/V2 feature work separately; do not blindly stage the worktree.

No commits are authorized now. frontend/AGENTS.md forbids rewriting published Lovable history.

## Recommendations

### MUST FIX

Resolve model-only routing versus overrides explicitly. Smallest alternative: use model choice directly, retain cart authorization guards that can reject an action without rerouting, return clarification for uncertain/invalid decisions, and supply selected-product/conversation context in state. Validate labeled named/reference/negated/cart/suggestion cases before removing existing recovery logic. Existing tests cannot certify model-only routing.

Define uncertainty/escalation/action policy from labeled V2 shopping evidence and appropriate answer_confidence, without invented threshold. Validate cart/storage/context numeric/shape bounds, secure ingestion if exposed, and clarify simulated checkout status. Complete connected-browser acceptance. Enforce revision/provenance at integration boundaries.

### SHOULD IMPROVE

Keep current V2 checkpoint/provider. Measure cold/warm, inference lock queue, tokenization, SQL and generation at realistic concurrency. Worker-pool patch requires production load testing. Persistent process, Sessions, suggestion caches and Ollama keep_alive already exist.

Profile listing payload/ILIKE query plans before indexes. Safely experiment with omitting unused escalation question only under decision parity checks; it can alter decisions. Preserve database revalidation for cart mutations. Pin reproducible service requirements and archive model/results outside Git.

### OPTIONAL OPTIMIZATION

Thread tuning/warm-up/export/quantization require isolated labeled parity work and separate model authorization. No automatic download/training/provider replacement. Cache decisions only with checkpoint/revision/questions/full-state keys; never stale catalog/cart facts. Batching can increase interactive waiting. Regex fast paths violate this task constraint and are not recommended.

## Lead-facing executive summary

Current ShopAI uses React, FastAPI, PostgreSQL and pinned Python Laya V2 with optional llama3.2 generation. Targeted fixes correct stale setup, malformed decision handling, confidence preservation, pagination/TV navigation and event-loop blocking; no model/provider/database redesign occurred.

Historical base→ONNX specialist accuracy improves 35.90%→76.50% (+812 correct), while mean HTTP latency increases 8.85→11.64 seconds and ECE worsens. Saved Python V2 is 78.80% (1576/2000) with 7.87-second mean case latency; these different runtime experiments are not controlled production comparisons. Counts were freshly verified, inference not rerun.

Automated checks/builds pass and local database is consistent. Production readiness still requires model-only routing resolution, uncertainty policy, input/cart validation, honest checkout boundaries, browser acceptance and concurrent latency measurement.

## VERIFIED FACTS / INFERENCES / NOT VERIFIED

**VERIFIED:** live V2 identity/port, allowlisted configured endpoint, PostgreSQL integrity, recounted saved benchmarks, fresh checks/exit statuses, API outputs, source overrides/confidence semantics/blocking calls and targeted edits.

**INFERENCES:** concurrent blocking chat substantially contributed to suggestion pre-handler delay; worker-pool change should improve unrelated request responsiveness. Tests prove yielding, not throughput improvement. Generic accuracy may help shopping, magnitude unknown.

**NOT VERIFIED:** every UI feature, production runtime/traffic/security, loaded weight hashes, matched fresh model benchmarks, shopping calibration, exhaustive absence of secrets, retailer facts/policy freshness, payments/orders/delivery, complete exhaustive code/dependency/model audit.

## Evidence and inspected files

Fresh [evidence JSON](shopai_stabilization_evidence_2026-10-09.json), [backend tests](threadtests_2026-10-09.log), [concurrency tests](concurrency_2026-10-09.log), [frontend tests](helpers_2026-10-09.log), [build](finalbuild2_2026-10-09.log), [TypeScript](finaltypes2_2026-10-09.log). October7 documentation was preserved.

Exact inspected-file inventory and contribution are attached in shopai_inspected_files_2026-10-09.md. Reads include selected sections where indicated; enumeration/secret scan is not exhaustive semantic review.
