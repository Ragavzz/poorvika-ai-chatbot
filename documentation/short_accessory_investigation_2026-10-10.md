# Poorvika ShopAI — short accessory search investigation

10 October 2026, Asia/Calcutta. Read the [Sony report](sony_search_investigation_2026-10-10.md) and [previous accessory report](accessory_compatibility_investigation_2026-10-10.md) before changes. Existing source changes and reports were preserved. No staging, commit, push, reset, clean, dependency installation, model download, provider change or database import.

**Verified:** short and long requests through the real /api/chat endpoint return the M.A protector at ₹999, Out of Stock. A real short add request is rejected without a cart command. Backend 138 executions, frontend 18 tests, TypeScript, production build and diff check pass. **Browser acceptance is blocked.**

## Exact root cause and before/after filters

Short request: **Show me the Samsung Tab S7 screen protector**.

Before changing production code, both a plain HTTP request and a request serialized with frontend-equivalent recent-product/cart context returned the reported false empty result. The existing API runtime log confirms the filters and zero results. A separate read-only PostgreSQL probe captured parameterized SQL, results and real Laya orchestration before editing.

| Field/stage | Before | After |
|---|---|---|
| Genuine Laya V2 decision in read-only trace | add_to_cart, confidence 0.2072 | Same decision/confidence |
| Effective action | product_search via existing discovery guard | Same existing guard |
| brand | Samsung | null |
| category | null | null |
| min_price / max_price | null / null | null / null |
| search_term | tab s7 screen protector | samsung tab s7 screen protector |
| exact_name candidate | absent | the samsung tab s7 screen protector |
| SQL text terms | tab, screen, protector | samsung, tab, **s7**, screen, protector |
| SQL row count | 0 | 1 |
| Final catalog reply | Incorrect empty result | M.A, ₹999, Out of Stock |

The earlier compatibility policy activated only when an accessory preceded **for**, **compatible with** or **fits**. Without a connector, manufacturer extraction scanned the entire short request and inferred Samsung, then removed Samsung from text terms. PostgreSQL applied manufacturer Samsung to a row whose actual brand is M.A. This excluded the row. A second defect in this path was that existing retrieval retains short alphanumeric identifiers only when accessory exact-name handling is enabled; S7 remained in ChatService's search_term but was omitted from SQL before the fix.

Tab was retained. S7 was not interpreted as price. Category was null, so no category predicate excluded the stored **Temper glass** row. This did not require a category remapping change.

Evidence: [before HTTP payloads/results](short_accessory_2026-10-10/before_live.json), [existing API log excerpt](short_accessory_2026-10-10/before_api_runtime_excerpt.log), [before SQL/real-service trace](short_accessory_2026-10-10/before_trace.log), [after SQL/real-service trace](short_accessory_2026-10-10/after_trace.log).

## UI serialization and complete flow

Source inspection shows ChatbotPanel trims the visible message, appends a shopai_client_context JSON block with recent_product_ids/cart, and calls api.ts. api.ts posts **{message: wireMessage}** to FastAPI /api/chat. Selected suggestion context is attached only on the suggestion-click path. FastAPI passes ChatRequest to ChatService; context is stripped before Laya, which receives the clean message in state.message with the existing questions contract.

Real V2 returned add_to_cart for this discovery request. The existing natural-product-discovery guard selected product_search. This task did not alter model, questions, confidence or action routing. ChatService extracted filters; ProductSearchTool issued the bounded parameterized SQLAlchemy query against PostgreSQL; deterministic formatting used the returned row and skipped Ollama.

After the fix, both recent selection of the protector and a different Sony selection with a nonempty cart returned the same named protector. Source and these API payloads rule out context as a necessary cause of the reproduced failure. **The user's actual browser network request was not captured.** Frontend-equivalent serialization is API evidence, not rendered browser acceptance.

## General policy and minimal fix

When an existing accessory noun occurs and the query contains **known device brand + device family + alphanumeric model**, treat that phrase as device compatibility even without an explicit connector. Device families include tablet/tab, phone, Galaxy, iPad/iPhone, Pixel and Surface forms; models require both letters and digits. The manufacturer vocabulary comes from the existing KNOWN_BRANDS list. There is no product ID, product-name or Samsung/S7-specific production branch.

Remove the recognized device phrase only from the text used to infer accessory manufacturer/category. Preserve it in product-search text. A separate manufacturer outside that phrase remains active: Inbase Samsung Tab A7 Lite flip cover retains Inbase; Samsung Silicone Case For Galaxy A54 retains Samsung; an explicit **by Samsung** on the short protector request still applies Samsung and correctly finds nothing.

Enable the existing accessory name-candidate path so existing ProductSearchTool retains short device identifiers. The short candidate is not equal to the full catalog name: this successful result comes from the normal all-term text match, including S7. The long request still uses the existing exact-name alternative. No additional catalog scan, query, fuzzy matching or tool change was added.

The existing expression remains **attribute constraints AND (exact name OR all-term text match)**. Manufacturer, category, price, rating, discount and stock constraints remain outside the alternative and cannot be bypassed. Cart stock checks and membership/mutation safeguards were not modified.

## Regression evidence

The original full backend suite passed **124 executions before editing**, despite this reproduced failure. Fourteen new tests then ran against the old production source and produced **six assertion failures**. After the fix, the combined short/previous accessory/Sony suite passed 33 executions, and the final complete suite passed 138 executions.

The fourteen new tests use the existing isolated real-catalog SQLite fixture and **mock Laya choices**. They cover short and long names; Samsung manufacturer; Inbase implicit compatibility; S9/S6/S70 exclusion; genuinely absent accessory and no selected-product fallback; out-of-stock add and quantity increase without changed context/markers; irrelevant selected-product context; explicit manufacturer/category/budget; exact-name alternatives under brand/category/minimum/maximum price/in-stock/rating/discount restrictions; and Sony under ₹1,000 variants. Existing tests were unchanged. Counts are test executions, not unique end-to-end user journeys; existing inherited tests repeat. The full suite includes existing real-service tests as well as mocks.

| Check actually performed | Result | Evidence |
|---|---|---|
| Backend complete regression suite | 138 executions, exit 0 | [backend.log](short_accessory_2026-10-10/backend.log) |
| Frontend cart/suggestion/click helper tests | 18 pass, exit 0 | [frontend.log](short_accessory_2026-10-10/frontend.log) |
| TypeScript --noEmit | exit 0 | [types.log](short_accessory_2026-10-10/types.log) |
| Vite production build | exit 0 | [build.log](short_accessory_2026-10-10/build.log) |
| git diff --check | exit 0 | [diff_check.log](short_accessory_2026-10-10/diff_check.log) |
| Actual real API rejection through frontend cart helper | unchanged in-memory cart; zero lookup/mutation callbacks | [client_cart.log](short_accessory_2026-10-10/client_cart.log) |
| Browser UI | BLOCKED: no surfaces; iab creation reports Browser is not available: iab | No browser acceptance performed |

Existing Starlette/httpx deprecation, unclosed SQLite resource and build chunk/plugin/WASM warnings remain. Git emitted LF/CRLF notices but no diff-check error.

Commands used with existing installed tools, Python cwd backend and Node cwd frontend:

```powershell
..\.venv\Scripts\python.exe -m unittest test_backend test_chat_regressions test_suggestions test_suggestion_click test_laya_contract test_chat_concurrency test_search_budget_regressions test_accessory_compatibility test_short_accessory
node --test tests/chat-cart.test.cjs tests/product-suggestions.test.cjs tests/suggestion-click.test.cjs
node node_modules/typescript/bin/tsc --noEmit
node node_modules/vite/bin/vite.js build
git diff --check
```

## Real-service API acceptance and cart safety

All thirteen live requests below returned HTTP 200 against the updated local FastAPI on port 8000 and existing real Laya V2/PostgreSQL services. [Exact payloads/responses/timings](short_accessory_2026-10-10/after_live.json) and [independent public catalog checks](short_accessory_2026-10-10/catalog_checks.json) are retained.

| Request | Actual result | HTTP ms |
|---|---|---:|
| Short screen-protector query | M.A, ₹999, Out of Stock | 2687 |
| Long exact query from previous report | Same real row, Out of Stock | 3209 |
| Short with selected protector context | Same real row | 2403 |
| Short with different selection and existing Sony cart | Same real row | 2707 |
| Add the Samsung Tab S7 screen protector to my cart | Explicit out-of-stock refusal; no add/cart-action marker | 2634 |
| Samsung Silicone Case For Galaxy A54 5G ( Lime ) | Samsung, ₹1499, In Stock | 2906 |
| Inbase Samsung Tab A7 Lite flip cover | Inbase, ₹899, In Stock | 2457 |
| Samsung Tab S9 screen protector | No result | 2671 |
| Samsung Tab UnknownDevice999 holographic protector | No result | 2585 |
| Short request by Samsung | No result; manufacturer restriction retained | 2912 |
| Short request under 500 rupees | No result; price restriction retained | 2588 |
| Short request in category Mobiles | No result; category restriction retained | 2606 |
| Sony earphones under 1000 rupees | Sony MDR-EX15AP, ₹829, In Stock | 3008 |

Read-only PostgreSQL independently verified the protector's actual brand M.A, category Temper glass, numeric price 999, stock 0 and in_stock false. Public product details return inStock false. The real add rejection was replayed through the existing actual frontend applyChatCartResponse helper with the nonempty Sony cart carried in that request. The helper left the cart byte-for-byte unchanged and called no lookup/add/remove/update callback. This is stronger than marker inspection alone, but **does not certify browser localStorage or rendered cart state**. Mocked backend tests independently cover out-of-stock quantity-increase rejection without a cart command.

The separate after-probe observed one Laya call, one search query and no Ollama call. Timings were Laya 5500.7 ms, SQL 11.5 ms, search 14.2 ms including SQL; these are not the stage breakdown of the listed HTTP samples and establish no production latency improvement.

The existing local Uvicorn verification process was reloaded to apply code, with --lifespan off to prevent startup ingestion. V2 was not restarted or changed; identity/loaded health and existing pinned revision were verified. Database probes used a read-only transaction. Local API verification remains running with reload enabled; this is not a production deployment.

## Exact files changed and preservation

Production: **backend/app/services/chat_service.py** — extend accessory filter scoping to implicit device references. [Task-only diff](short_accessory_2026-10-10/task_delta.diff) is separate from prior work. ProductSearchTool is unchanged in this task.

New regression: **backend/test_short_accessory.py** — fourteen tests.

New report: **documentation/short_accessory_investigation_2026-10-10.md** — this file.

New evidence under **documentation/short_accessory_2026-10-10/**:

```text
initial_status.txt
original_chat.txt
original_tool.txt
preservation_hashes.json
preservation_results.json
before_live.json
before_api_runtime_excerpt.log
probe.py
before_trace.log
baseline.log
before_target.log
after_target.log
backend.log
frontend.log
types.log
build.log
api_runtime.log
after_trace.log
after_live.json
catalog_checks.json
health.json
browser_status.json
client_cart_probe.cjs
client_cart.log
task_delta.diff
git_status.txt
diff_check.log
```

Existing active service logs documentation/accessory_compatibility_2026-10-10/backend_runtime.log and laya_restart.log naturally appended request output during verification; they were not rewritten. SHA-256 snapshots of existing Git-enumerated tracked/nonignored untracked files showed only these runtime logs and the intended ChatService source changed. Earlier reports, ProductSearchTool, frontend source and previous tests remained byte-identical. This snapshot excludes ignored configuration/model/build files and is not an exhaustive filesystem audit.

A generated untracked Windows cache appeared at **%SystemDrive%/ProgramData/Microsoft/Windows/Caches/** with four .db files during local tooling. It was inspected and left untouched under the user's no-clean requirement; it is not source and should not be staged. Build/test generated ignored artifacts are also not source changes.

Initial and final Git status have the same fourteen modified tracked paths: ChatService was already modified before this task. New test/report/evidence were added alongside existing untracked work. Final source delta, full existing diff and status were inspected; the staged diff is empty. Branch main, HEAD fe36d13. No stage, commit, push, reset or clean occurred.

## Remaining limitations

Actual browser network capture, rendered chatbot/cart behavior, keyboard/mobile/layout/localStorage acceptance are blocked by unavailable browser tooling. The reported real browser failure was reproduced by plain and frontend-equivalent API requests, not by this session's UI automation.

Implicit compatibility detection is bounded by existing accessory nouns, known brands, supported device-family forms and letter/digit models. Other grammar, numeric-only models, unknown brands, misspellings and ambiguous manufacturer intent need labeled follow-up rather than broadening filters indiscriminately. Matching a catalog device description is not proof of physical fit for every Tab S7 variant; the response retains the full catalog name and claims no new compatibility facts.

The real model still chooses low-confidence add_to_cart for the short discovery query, recovered by the pre-existing guard. Model-only routing and calibrated uncertainty issues in the previous audit remain unresolved. This task changes filter resolution only. Production load, exhaustive language coverage and current retailer fulfillment were not tested.
