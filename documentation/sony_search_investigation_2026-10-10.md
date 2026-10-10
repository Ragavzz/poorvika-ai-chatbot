# Poorvika ShopAI — Sony search investigation

10 October 2026, Asia/Calcutta. Continuous local investigation; captured runtime logs retain their original 9 October timestamps. This report supplements the existing [stabilization audit](shopai_stabilization_audit_2026-10-09.md), which was preserved.

**PASS: the exact Sony search failure is reproduced, explained and fixed.** The live chatbot now returns Sony MDR-EX15AP Earphone ( Black ), ₹829, In Stock. **FAIL: a separate named accessory search remains unresolved. BLOCKED: real browser acceptance.** This is not a complete production-readiness certification.

## Root cause and smallest fix

The first incorrect stage was **ChatService._filters**, before PostgreSQL execution. For `Show me Sony earphones under 1000 rupees`, Laya returned a genuine supported **product_search** decision, observed confidence **0.8949**. The effective action remained product_search: the existing recovery rules did not change this action.

Brand Sony, category Headphones and max_price 1000 were correct. The existing budget-removal expression consumed `under 1000` but left `rupees`. Existing token normalization changed that to **search_term="rupee"**. ProductSearchTool then correctly implemented the supplied filters as:

```sql
category ILIKE '%Headphones%'
AND brand ILIKE '%Sony%'
AND price <= 1000
AND (name ILIKE '%rupee%' OR brand ILIKE '%rupee%'
     OR category ILIKE '%rupee%' OR model ILIKE '%rupee%'
     OR description ILIKE '%rupee%')
```

The actual ORM statement uses bound parameters; this abbreviated illustration shows their values. The extra text predicate excluded the matching product and produced zero rows. The response formatter faithfully formatted that erroneous empty result. No missing data, price/stock mismatch, swallowed exception, ranking exclusion or pagination issue explained this failure.

**Two source lines changed**, both in [chat_service.py](../backend/app/services/chat_service.py):
- The existing budget cleanup now consumes rupee/rupees, Rs and INR units adjacent to a recognized budget amount, including currency words before the number. It does not erase arbitrary product terms.
- `all` joins the existing ignored listing words. A second reproduced failure, `Show me all Sony earphones`, previously required search_term="all" and returned zero rows.

After cleanup, the exact query has **search_term=null**. The same search tool and SQLAlchemy filters return the matching row. There is no Sony-specific production branch, change to action routing, relaxed stock check, database write, provider/model change or dependency addition.

## Independent evidence and request trace

| Check | Status | Observed evidence |
|---|---|---|
| A: JSONL | PASS | data/poorvika_products.jsonl contains id sony-mdr-ex15ap-earphone-black, Sony, online_price 829, mrp 890, stock 64, schema.org/InStock. |
| B: PostgreSQL | PASS | Independent read-only transaction returns the same ID/name/brand; category Headphones, numeric price and online_price 829.0, mrp 890.0, stock 64, in_stock true. |
| C: search tool | PASS | search_products(brand="Sony", category="Headphones", max_price=1000) returned the Sony row before any fix. Parsed filters returned zero before and one after. |
| D: public catalog API | PASS | GET /api/products/search?brand=Sony&category=Headphones&max_price=1000 returns HTTP 200 and the matching ID, price 829, originalPrice 890, inStock true. |
| E: Laya V2 | PASS | Live 5056 health reports loaded Mass121/laya-typed-decisions-v2, revision 6fb41711ea5ff81097e6fc09ccebf31138b06e4d. Real adapter call for the exact query returns product_search. |
| F: extracted filters | FAIL before / PASS after | Brand/category/budget unchanged. Spurious search_term "rupee" becomes null. |
| G: final chat API | FAIL before / PASS after | POST /api/chat with JSON message returned the reported empty-result text before; after it returns the Sony product, ₹829, In Stock and its SHOPAI_PRODUCTS marker. |
| React browser display | BLOCKED | No enabled browser/app surfaces were available; no rendered UI acceptance was performed. |

The model maps to the existing `products` table; search uses its `price` column. Read-only probes used the configured PostgreSQL engine directly, rather than the application's possible SQLite fallback. Stored punctuation/spacing does not prevent this brand/category search. The row is in stock. Existing search limit five includes it once the stray term is removed.

Actual settings loading uses **backend/.env**; **backend/app/.env does not exist**. No private configuration values or connection string are included here. The existing endpoint is Python V2 on 5056. The adapter sends state and questions, validates answers.intent, and preserves separate confidence meanings. The old ONNX service was not substituted. No thresholds or confidence values were invented.

Source trace: ChatbotPanel → frontend/src/services/api.ts → JSON POST /api/chat → backend/app/routes/chat.py → ChatService → laya_client.py → Python V2 /decide → validated action → _filters → app/tools/product_search_tool.py → parameterized SQLAlchemy/PostgreSQL → deterministic catalog table and product marker → frontend marker handling and Streamdown. The frontend source retains context serialization and rendering; source inspection is not proof of actual DOM behavior.

Real dependency probes captured the service's existing logs for Laya choice, effective action, filters, SQL result count and generation skip. This was a fresh process using current source and real services, not a claim that logs were retrieved from the already-running Uvicorn console. No permanent diagnostic logging was added.

Inspected sources include backend config/database/model/schema/routes, laya_client/chat_service/product_search_tool/ollama_service, laya_v2_service/service.py and shopai_questions.json, frontend API/chatbot/popup/context helpers, existing tests, dataset and prior audit/evidence. Category synonyms map earphones to Headphones; this is a broad catalog category and can include headsets. Its existing behavior was preserved.

## Before and after automated verification

| Check | Before | After |
|---|---|---|
| Existing backend suite, including suggestions/click/cart/Laya/concurrency | PASS: 105 executions | PASS: 109 including four new tests |
| New targeted regression tests | FAIL: four tests, seven assertion/subtest failures | PASS: four tests |
| Frontend cart/suggestion/popup-click harness tests | PASS: 18 | PASS: 18 |
| TypeScript | NOT TESTED before in this investigation | PASS: exit 0 |
| Production build | NOT TESTED before in this investigation | PASS: exit 0 |
| git diff --check | NOT TESTED before in this investigation | PASS: exit 0 |

Counts are test executions, not 109 unique user scenarios; the suggestion-click class inherits and repeats tests. Existing tests were not changed, weakened or skipped. The original suite passing while the exact query failed demonstrated its coverage gap.

The new isolated real-catalog SQLite fixture tests cover eight currency variants, the all modifier, preservation of a named model qualifier, genuinely empty ₹1 searches, and grounded chat formatting after a mocked product_search decision. They assert one decision call and no generation call. Real Laya/PostgreSQL/API verification is separate from these mocked unit tests.

Commands used with existing installed tooling, with cwd backend for Python and frontend for Node:

```powershell
..\.venv\Scripts\python.exe -m unittest test_backend test_chat_regressions test_suggestions test_suggestion_click test_laya_contract test_chat_concurrency
..\.venv\Scripts\python.exe -m unittest test_search_budget_regressions
..\.venv\Scripts\python.exe -m unittest test_backend test_chat_regressions test_suggestions test_suggestion_click test_laya_contract test_chat_concurrency test_search_budget_regressions
node --test tests/chat-cart.test.cjs tests/product-suggestions.test.cjs tests/suggestion-click.test.cjs
node node_modules/typescript/bin/tsc --noEmit
node node_modules/vite/bin/vite.js build
git diff --check
```

The shell execution tool was unavailable; equivalent child_process executions ran these installed tools without installing anything. Full output is retained in [verification.log](sony_search_2026-10-10/verification.log). Existing warnings include Starlette/httpx deprecation, unclosed SQLite resources, large build chunks, plugin overhead, ignored inlineDynamicImports and WASM module fallback.

## All ten requested live queries

Every listed request reached the running backend on 8000 and returned HTTP 200. PASS means expected application behavior and catalog grounding, not merely HTTP success. Returned product IDs were fetched independently through the public product-detail API and compared to response names/prices and query constraints.

| Query | Status | Result | HTTP ms |
|---|---|---|---:|
| Show me Sony earphones under 1000 rupees | PASS | Sony MDR-EX15AP, ₹829, in stock | 3749.4 |
| Find Sony earphones below ₹1000 | PASS | Same Sony row and price | 2465.5 |
| Show me all Sony earphones | PASS | Five Sony Headphones rows, including MDR-EX15AP; existing top-five limit | 2402.1 |
| Find earphones under 1000 | PASS | Five Headphones rows, all prices <=1000 | 2343.0 |
| Show me Samsung phones under 20000 | PASS | Five Samsung Mobiles rows, all prices <=20000 | 2603.8 |
| Recommend a phone for gaming | PASS | Five real in-stock Mobiles; rating-based ordering, explicit lack of verified gaming-performance comparison | 2391.3 |
| Tell me the specifications of Sony MDR-EX15AP Earphone | PASS | Correct row, price/MRP/stock and catalog specifications | 2539.7 |
| Show me products from a nonexistent brand | PASS | Empty result; independent nonexistent-brand catalog search also [] | 2229.3 |
| Show Sony earphones under 1 rupee | PASS | Genuine empty result; independent Sony/Headphones/max_price=1 search also [] | 2383.6 |
| Show me 2.5D Clear Tempered Glass Screenshot Protector For Samsung Tab S7 Plus 12.4 Inch/T735NE S7 FE/Samsung S7 FE ( Transparent ) | FAIL | Existing out-of-stock row is missed | 2983.2 |

The out-of-stock product exists with ID `2-5d-clear-tempered-glass-screen-protector-for-samsung-tab-s7-plus-12-4-inch`, catalog brand **M.A**, price ₹999, stock **0**, in_stock **false**. A read-only filter probe infers **brand Samsung** from the compatible device in its name; its generated search also retains many full-name terms. The Samsung brand predicate excludes the M.A row. It is therefore not a genuine catalog absence. This separate accessory/manufacturer-versus-compatibility problem was recorded, not masked by relaxed stock checks or a product-specific fallback. Correcting it needs a targeted ambiguity policy and labeled accessory cases; the smallest next step is distinguish an exact catalog-name lookup from brand-filter inference, with cart safeguards preserved.

## Live services, suggestions and browser limits

**PASS:** backend API and Python V2 available; read-only real PostgreSQL query works; frontend HTTP 8080 returns 200. Exact Sony direct search and chat are both verified.

**PASS:** a live /api/chat/suggestions request using the Sony catalog context returned four model-generated questions, HTTP 200. Round trip **20591.5 ms**, server handler **20534.326 ms**, Ollama client call **20523.551 ms**, reported generation subcomponent **3470.693 ms**. These overlapping timings are not additive. Ollama generation is not required by the Sony catalog search. Existing configured model llama3.2:latest remains unchanged. Passing question validation does not establish recommendation correctness.

**PASS:** suggestion-popup/click and cart safety regression harnesses.
**BLOCKED:** connected browser rendering, actual popup click, real cart mutation, mobile/layout/keyboard acceptance.
**NOT TESTED:** actual browser refresh/multitab persistence, production load, retailer fulfillment freshness, payments/orders, ingestion/import. No database import or production restart was executed.

## Response time measurements

Ten sequential repeated warm **live HTTP /api/chat** requests for the exact Sony query, after prior successful requests:

**4752.3, 3862.7, 3637.2, 2609.4, 2714.4, 2771.4, 2818.5, 2987.0, 2544.0, 3339.6 ms.**

All returned the correct Sony product. Median **2902.75 ms**. Empirical nearest-rank P95 **4752.3 ms** (with n=10 it equals the maximum; this small sample is not a reliable production tail estimate). No controlled before/after latency comparison was conducted, so no speedup claim is supported.

Separate calls to the actual async route handler in a fresh process, with real V2 and read-only PostgreSQL, captured its existing timing fields:

| Sample | Laya ms | Search tool ms | SQL ms, included in search | LLM | Handler total ms |
|---|---:|---:|---:|---|---:|
| 1 | 4157.9 | 24.5 | 20.6 | Skipped | 4190.2 |
| 2 | 2437.2 | 3.4 | 2.5 | Skipped | 2441.3 |
| 3 | 2423.7 | 2.9 | 2.2 | Skipped | 2427.2 |

These are distinct probes, not the stage decomposition of the ten HTTP samples. Handler totals exclude external transport and framework ingress. All three made **one Laya call, one product query, zero Ollama calls** and returned the correct row. Laya dominates these samples. Timing includes client/queue/inference time; model compute is not independently isolated. The parser change adds no extra model or database calls. No performance architecture change was justified. Existing worker-pool behavior was preserved; production concurrent throughput remains NOT TESTED.

To reproduce the read-only stage probe from backend:
`..\.venv\Scripts\python.exe ..\documentation\sony_search_2026-10-10\timing_probe.py`.

## Every file changed by this investigation

| File | Reason |
|---|---|
| backend/app/services/chat_service.py | Two general filter-cleanup lines described above; retains all previous edits. |
| backend/test_search_budget_regressions.py | Four focused regression tests, added after reproducing the bug. |
| documentation/sony_search_investigation_2026-10-10.md | This report. |
| documentation/sony_search_2026-10-10/evidence.json | Before/after APIs, SQL/filter traces, catalog comparison, health, ten regressions, warm/stage timings and Git evidence. |
| documentation/sony_search_2026-10-10/verification.log | Before/after tests, typecheck and build output, sensitive configuration lines redacted if present. |
| documentation/sony_search_2026-10-10/timing_probe.py | Reproducible route timing probe, real dependencies and read-only DB transactions; no credentials embedded. |

No other pre-existing source/document file was edited by this task. Build/test generated ignored artifacts are not included in this source-change list.

## Git and remaining limitations

**PASS:** branch main, HEAD fe36d13, index diff empty. Initial worktree already had **13 modified tracked files** and extensive untracked V2/suggestion/evaluation/documentation work. Final status still has those 13 modified tracked files, plus the new regression test/documentation. The chat service was already modified when this task began; the investigation's own delta is only the two lines above.

SHA-256 comparisons of **273 pre-existing tracked/nonignored untracked files** found only the intended chat_service.py change. Prior audit/evidence and existing tests were preserved byte-for-byte within this scope. Ignored environment/model/build files are outside that hash audit; private environment/model files were not edited. Full Git status snapshots and the exact task-only source delta are in evidence.json.

**PASS: nothing staged, committed or pushed.** No destructive Git operation, model download/training/provider swap or database write/import was performed.

**FAIL remaining:** accessory compatibility/brand ambiguity in the tenth query.
**BLOCKED:** browser acceptance.
**NOT TESTED:** full production/end-to-end certification and statistical latency profiling. Prior audit concerns—existing action overrides, uncalibrated uncertainty policy, malformed context/storage bounds, ingestion exposure and simulated checkout—remain outside this minimal search fix.

[Machine-readable evidence](sony_search_2026-10-10/evidence.json) and [verification log](sony_search_2026-10-10/verification.log) retain the supporting results.
