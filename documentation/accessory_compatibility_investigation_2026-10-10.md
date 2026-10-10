# Poorvika ShopAI — accessory compatibility search fix

10 October 2026, Asia/Calcutta. Read the [Sony investigation](sony_search_investigation_2026-10-10.md) and its evidence before editing. Existing work was retained. No staging, commit, push, reset, Git clean, model/provider change, dependency installation or database import.

**PASS:** the exact accessory query returns the real M.A protector at ₹999, explicitly Out of Stock. A real add-to-cart request is rejected without an add marker. **PASS:** final backend/frontend tests, TypeScript, production build and diff check. **BLOCKED:** browser acceptance.

## Root cause and complete trace

Exact request:

`Show me 2.5D Clear Tempered Glass Screenshot Protector For Samsung Tab S7 Plus 12.4 Inch/T735NE S7 FE/Samsung S7 FE ( Transparent )`

Before editing, the running /api/chat endpoint returned HTTP 200 with the incorrect empty-search text. Independent current-source/read-only PostgreSQL orchestration reproduced this:

1. Laya V2 returned **add_to_cart, confidence 0.0476**, not product_search.
2. The pre-existing natural-discovery guard changed the effective action to **product_search** because this was a “Show me” request. That existing guard was not changed.
3. _filters scanned the full name for brands, selected **Samsung**, and removed Samsung from the text terms.
4. ProductSearchTool ANDed the inferred Samsung manufacturer predicate with the remaining name terms.
5. The catalog row has **brand M.A**, so the manufacturer predicate excluded it. SQL returned zero rows; the formatter returned the empty-result message.

The first erroneous catalog stage was manufacturer extraction. Numeric model references can also be mistaken for an approximate-price phrase after “for”; the compatibility policy prevents that interpretation within the supported accessory form.

Fresh PostgreSQL verification after the fix returned:
- ID: 2-5d-clear-tempered-glass-screen-protector-for-samsung-tab-s7-plus-12-4-inch
- Brand M.A, category Temper glass
- Numeric price 999.0, stock 0, in_stock false
- Exact stored name matches the requested name, including “Screenshot”.

Post-fix real-service trace observed the same Laya choice/confidence and existing recovery, followed by **brand=null**, retained Samsung/device terms, an exact-name candidate, **one matching database row**, and deterministic catalog formatting. No Ollama generation was invoked. The genuine model decision was neither fabricated nor replaced by a new router.

[Before observations](accessory_compatibility_2026-10-10/before.json), [current read-only trace](accessory_compatibility_2026-10-10/trace.log), [live responses](accessory_compatibility_2026-10-10/live.json).

## General policy implemented

For descriptions that name an accessory before **for**, **compatible with** or **fits**:

- Infer manufacturer and product category from the accessory description before the compatibility connector. A device brand after the connector is not treated as the accessory's manufacturer.
- Retain the compatible brand and device/model words as text constraints. Samsung-branded accessories retain Samsung as manufacturer; Inbase accessories for Samsung retain Inbase.
- Ignore a command introduction such as “Search for” when identifying the compatibility connector. Keep device identifiers such as S7 as meaningful search terms.
- Do not interpret the compatibility “for S7” as an approximate-price instruction or remove the device target as a recommendation use case. Explicit under/above budget constraints remain active.
- Preserve the full accessory-name candidate, stripping supported command wrappers, cart suffix and budget phrase. Add a case-insensitive, edge-trimmed exact catalog-name equality as an **alternate text match** and prioritize it in default search ordering.

The database expression remains:

`manufacturer/category/price/stock/rating/discount constraints AND (exact name OR existing all-term text match)`

Exact-name matching never bypasses those attribute filters. Recommendations still require in-stock rows and retain their rating sort. The optional tool argument is appended to the signature, preserving existing callers. Everything is executed in the existing bounded, parameterized SQLAlchemy query, without a separate catalog scan or additional retrieval.

This is filter/name resolution after Laya; no new keyword action routing was introduced. No product ID, brand-specific case or fabricated compatibility specification is embedded in production code.

## Before/after and requested regression coverage

| Scenario | Before | After |
|---|---|---|
| Exact M.A screen protector | FAIL: zero results | PASS: correct row, ₹999, Out of Stock |
| Samsung-manufactured accessory | Tested by new regression | PASS: Samsung Silicone Case For Galaxy A54, ₹1499 |
| Other manufacturer's Samsung-compatible accessory | FAIL: inferred Samsung rather than Inbase | PASS: Inbase Flip Cover for Samsung Tab A7 Lite, ₹899 |
| Named nonexistent device accessory | Genuine absence retained | PASS: no result; explicit named add does not fall back to recent selection |
| Out-of-stock named add | Failed to resolve product; no add issued | PASS: resolves real row, explicitly refuses add; no SHOPAI_ADD_TO_CART |
| Out-of-stock cart quantity increase | Failed to resolve item | PASS: stock rejection; no cart mutation marker |
| In-stock accessory add | Failed named resolution in new regression | PASS in isolated regression: normal add marker retained |
| Sony under ₹1000 searches | PASS baseline | PASS live and regressions: Sony MDR-EX15AP at ₹829 |
| Contradictory brand/category/budget/in-stock filters with exact name | New contract coverage | PASS: exact name cannot bypass them |
| Compatible-device recommendation and short identifiers | Additional coverage | PASS: device target retained; S9 does not return the S7 protector |

Fifteen new tests use the existing real-catalog isolated SQLite fixture with controlled Laya decisions. They do not write to the active database. All existing tests are unchanged.

The original **109-execution backend suite passed before editing**, despite the accessory failure. The initial twelve new tests failed with **seven assertion failures and six errors**; errors include exercising the not-yet-implemented exact_name argument. Two policy tests and one command-prefix test were then added, and the short-model test expanded. Before observations are retained as selected tool-output values rather than represented as a complete raw baseline log.

## Live HTTP acceptance

Each request below returned HTTP 200. Matching product records were independently retrieved through the public product-detail endpoint; prices, brands and availability match the responses.

| Request | Status/result | Round trip ms |
|---|---|---:|
| Exact screen-protector query above | PASS: M.A, ₹999, Out of Stock, real product marker | 3284 |
| Add the exact protector to my cart | PASS: explicit out-of-stock refusal, no add marker | 2907 |
| Show me Samsung Silicone Case For Galaxy A54 5G ( Lime ) | PASS: Samsung, ₹1499, In Stock | 2746 |
| Show me Inbase Flip Cover For Samsung Tab A7 Lite 8.7 Inch ( Black ) | PASS: Inbase, ₹899, In Stock | 2662 |
| Show me Inbase Flip Cover For Samsung UnknownDevice999 ( Black ) | PASS: genuine empty result | 2761 |
| Show me Sony earphones under 1000 rupees | PASS: Sony MDR-EX15AP, ₹829, In Stock | 2472 |
| Find Sony earphones below ₹1000 | PASS: same Sony row | 2486 |

[Independent catalog checks](accessory_compatibility_2026-10-10/catalog_checks.json).

Separate read-only orchestration timings for the exact query: Laya **3194.1 ms**, search tool **31.2 ms**, SQL **23.9 ms** included in the tool measurement, **one Laya call, one search query, no Ollama call**. These are not the stage breakdown of the separate HTTP sample, and no speedup or production P95 claim is made.

The local services stopped during verification. One intermediate **123-execution run had one failed live integration assertion** due to Laya connection refused; isolated cases passed. Its [failed-run evidence](accessory_compatibility_2026-10-10/backend_service_unavailable.log) was preserved. V2 was restored from the existing cache with HF_HUB_OFFLINE and TRANSFORMERS_OFFLINE enabled. Health confirms the same model Mass121/laya-typed-decisions-v2, revision 6fb41711ea5ff81097e6fc09ccebf31138b06e4d, loaded on 5056. Cache file resolution messages do not represent an authorized download; offline mode was enforced.

A local verification Uvicorn process on 8000 used --lifespan off to avoid startup ingestion. PostgreSQL probes used SET TRANSACTION READ ONLY; no import or production restart occurred. The final complete suite then passed with the healthy real service. Local V2/API verification processes were left running.

## Required checks

| Check | Result | Evidence |
|---|---|---|
| Relevant backend suite including Laya, cart, suggestions/click, concurrency, Sony and accessory regressions | PASS: 124 executions, exit 0 | backend_final.log |
| Backend suite without the eight base/live integration tests | PASS: 115 executions, exit 0 | isolated.log |
| Frontend cart/suggestion/popup-click helper/hook tests | PASS: 18, exit 0 | frontend.log |
| TypeScript --noEmit | PASS: exit 0 | types.log |
| Production Vite build | PASS: exit 0 | build.log |
| git diff --check | PASS: exit 0 | diff_check.log |
| Real chatbot browser UI | BLOCKED: surfaces empty; iab creation returned “Browser is not available: iab” | actual browser acceptance not performed |

Counts are executions, not 124 unique user journeys; inherited existing tests repeat. Some tests use model mocks; the live API and read-only traces are separate evidence. Existing Starlette/httpx deprecation, SQLite resource and build chunk/plugin/WASM warnings remain.

Installed commands, cwd backend for Python and frontend for Node:

```powershell
..\.venv\Scripts\python.exe -m unittest test_backend test_chat_regressions test_suggestions test_suggestion_click test_laya_contract test_chat_concurrency test_search_budget_regressions test_accessory_compatibility
node --test tests/chat-cart.test.cjs tests/product-suggestions.test.cjs tests/suggestion-click.test.cjs
node node_modules/typescript/bin/tsc --noEmit
node node_modules/vite/bin/vite.js build
git diff --check
```

Reproducible read-only trace from backend:
`..\.venv\Scripts\python.exe ..\documentation\accessory_compatibility_2026-10-10\probe.py`.

## Exact files changed in this task

Production changes:
1. backend/app/services/chat_service.py — compatibility-scoped attributes, retained device terms and exact-name candidate, passed into the existing retrieval.
2. backend/app/tools/product_search_tool.py — optional constrained exact-name text alternative/default preference and short alphanumeric model terms on this path.

New regression file:
3. backend/test_accessory_compatibility.py — fifteen targeted catalog/filter/cart/Sony tests.

New report:
4. documentation/accessory_compatibility_investigation_2026-10-10.md — this report.

New evidence files, all under documentation/accessory_compatibility_2026-10-10/:
```text
backend.log
backend_final.log
backend_runtime.log
backend_service_unavailable.log
before.json
build.log
catalog_checks.json
diff_check.log
frontend.log
git_status.txt
health.json
isolated.log
isolated_before_short_model.log
laya_restart.log
live.json
probe.py
source_review.diff
trace.log
trace_service_unavailable.log
types.log
```

Logs retain successful and interrupted/service-unavailable checks; final results are identified above. source_review.diff is the complete unstaged diff of the two edited production files and includes pre-existing chat changes, not just this task's delta. Generated ignored test/build outputs are outside the source-change list. A new Windows cache directory created during local startup was inspected, verified inside the workspace and removed; pre-existing files were not cleaned.

## Git and remaining limitations

Branch **main**, HEAD **fe36d13**, empty staged/index diff. Initial status had thirteen modified tracked files; final status has fourteen, adding product_search_tool.py. ChatService was already modified; its prior Sony, worker-pool and suggestion work was retained. Existing untracked files, previous audit/evidence, tests and frontend work were not overwritten. Final source diff and status were inspected. Nothing staged, committed, pushed, reset or Git-cleaned.

**BLOCKED:** rendered UI, real browser cart changes, layout/keyboard/mobile acceptance. A backend marker/rejection is not a browser cart test.

**NOT TESTED:** production load/tail latency, exhaustive natural-language grammar, actual device fit or retailer stock freshness. The policy covers the documented accessory nouns and compatibility connectors; names with different grammar or misspellings remain subject to the existing strict text search. Exact equality does not add fuzzy matching. Known-manufacturer vocabulary remains the existing list; actual response brand always comes from the database.

The genuine Laya choice for the exact search is still low-confidence add_to_cart, corrected by the pre-existing discovery guard. Model-only routing/calibrated uncertainty concerns from the prior audit remain unresolved; they were not silently redesigned here. Stock, cart membership and mutation safeguards are unchanged and regression-tested.
