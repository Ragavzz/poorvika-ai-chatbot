# Chatbot end-to-end validation

Validation date: 10 October 2026. **Live API and client-handler checks passed; rendered browser acceptance is BLOCKED.** No browser was launched. This report does not certify visible popup placement or the user browser cart.

## Architecture and execution flow

`frontend/src/routes/__root.tsx` mounts QueryClientProvider, CartProvider, Chatbot and CartDrawer. Chatbot owns the popup selection callback and retains the lazily mounted ChatbotPanel. Panel sends `/api/chat` with session, selected product and cart context, then consumes cart/product markers using the existing helpers. CartProvider owns localStorage-backed cart state; backend cart text alone is not a cart mutation.

`backend/app/routes/chat.py` invokes ChatService, configured Laya V2 (`Mass121/laya-typed-decisions-v2`, port 5056), deterministic action validation and PostgreSQL product tools. Ollama `llama3.2:latest` on port 11434 generates greetings and informational answers. Search, comparisons, catalog details and cart arithmetic use actual data and deterministic formatting. The live catalog snapshot contains 508 PostgreSQL rows.

ProductSuggestionPopup observes product/search context and the shared product query, checks suggestion capabilities, and calls `/api/chat/suggestions`. Ollama generates the questions directly; Laya is not needed for this endpoint. Validation rejects malformed, duplicate, unsupported numeric and selected owned-feature claims. Successful results have a five-minute context/configuration-sensitive cache; failures are not cached. No hardcoded question fallback was added.

## Evidence and acceptance summary

| Feature | Result | Evidence / limit |
|---|---|---|
| Greetings, searches, filtering, details, comparison, context, stock, ambiguity | PASS live API | 29 actual requests below; catalog-backed assertions |
| Cart add, update, total, removal | PASS client-handler harness | Actual Chatbot/Panel/CartProvider code with live HTTP; isolated localStorage, not rendered browser |
| Popup generation for iPhone, Samsung phone, watch | PASS live API and sample review | Four distinct questions each, cache miss, one Ollama call each |
| Popup click and subsequent manual input | PASS client-handler harness | Actual callbacks/effects and live API; no DOM/browser interaction |
| Service failure behavior | PASS isolated contracts | Nine injected failures, not live service outages |
| Popup placement, paint timing, refresh/navigation, dismissal, overlap/reopening, rendered cart | BLOCKED | Browser and native computer-use providers unavailable |
| Backend suite / frontend suite / production build | PASS | 228 backend tests; 44 frontend tests; build succeeds |

## Live chat cases

Each row below was an HTTP 200 request against the running services. Raw predicted intent/confidence is retained independently of the resolved action. PASS applies to the scenario assertions, not general model accuracy. Full responses, probability vectors, request IDs, database rows, model/tool timings and cart before/after states are in [e2e-live-results.json](e2e-live-results.json).

| Input | Laya intent / confidence | Resolved action | Ollama calls | Source | HTTP | Latency ms | Result |
|---|---|---|---:|---|---:|---:|---|
| Hi | general_query / 0.5134 | general_query | 1 | ollama | 200 | 5901.3 | PASS |
| Hello | general_query / 0.9507 | general_query | 1 | ollama | 200 | 3702.5 | PASS |
| Good morning | general_query / 0.832 | general_query | 1 | ollama | 200 | 3306.7 | PASS |
| Show me Sony earphones under 1000 rupees | product_search / 0.8949 | product_search | 0 | deterministic_catalog | 200 | 2477.0 | PASS |
| Show me Samsung phones under 20000 | product_search / 0.9632 | product_search | 0 | deterministic_catalog | 200 | 2610.5 | PASS |
| Show me laptops | product_search / 0.1275 | product_search | 0 | deterministic_catalog | 200 | 2464.3 | PASS |
| Compare these two phones | recommendation / 0.3625 | comparison | 0 | deterministic_comparison | 200 | 2821.3 | PASS |
| Compare the first two phones | recommendation / 0.4134 | comparison | 0 | deterministic_comparison | 200 | 2527.0 | PASS |
| Tell me about the first product | product_details / 0.9789 | product_details | 0 | deterministic_catalog | 200 | 2300.7 | PASS |
| Tell me the specifications of this product | product_details / 0.914 | product_details | 0 | deterministic_catalog | 200 | 2458.4 | PASS |
| What is its price? | product_details / 0.1744 | product_details | 0 | deterministic_catalog | 200 | 2291.1 | PASS |
| Suggest a phone for photography | recommendation / 0.9917 | recommendation | 0 | deterministic_recommendation | 200 | 2385.2 | PASS |
| Is there a cheaper alternative? | add_to_cart / 0.1461 | product_search | 0 | deterministic_catalog | 200 | 2339.2 | PASS |
| Add this product to my cart | add_to_cart / 0.9901 | add_to_cart | 0 | cart_command | 200 | 2374.9 | PASS |
| Increase the quantity to two | add_to_cart / 0.9851 | cart_action | 0 | cart_command | 200 | 2271.1 | PASS |
| What is my current total? | cart_action / 0.1729 | cart_action | 0 | cart_state | 200 | 2316.0 | PASS |
| Reduce the quantity to one | add_to_cart / 0.7337 | cart_action | 0 | cart_command | 200 | 2248.9 | PASS |
| Remove this product from my cart | add_to_cart / 0.7974 | cart_action | 0 | cart_command | 200 | 2348.9 | PASS |
| Show me my cart | cart_action / 0.9733 | cart_action | 0 | cart_state | 200 | 2353.9 | PASS |
| Add this product to my cart | add_to_cart / 0.9901 | add_to_cart | 0 | deterministic_clarification | 200 | 2321.9 | PASS |
| Show me Samsung phones under 1 rupee | product_search / 0.9252 | product_search | 0 | deterministic_catalog | 200 | 2831.9 | PASS |
| Show me nonexistentmodelxyz123 | cart_action / 0.4088 | product_search | 0 | deterministic_catalog | 200 | 2651.4 | PASS |
| Tell me about this product | product_details / 0.9913 | product_details | 0 | deterministic_clarification | 200 | 2414.3 | PASS |
| Is this product suitable for heavy gaming due to its display and processor? | recommendation / 0.5239 | general_query | 1 | ollama | 200 | 20154.3 | PASS |
| What is its price? | product_details / 0.1744 | product_details | 0 | deterministic_catalog | 200 | 4069.0 | PASS |
| Add this product to my cart | add_to_cart / 0.9901 | add_to_cart | 0 | cart_command | 200 | 2947.4 | PASS |
| Increase the quantity to two | add_to_cart / 0.9851 | cart_action | 0 | cart_command | 200 | 2454.2 | PASS |
| What is my current total? | cart_action / 0.1729 | cart_action | 0 | cart_state | 200 | 2320.1 | PASS |
| Remove this product from my cart | add_to_cart / 0.7974 | cart_action | 0 | cart_command | 200 | 2512.9 | PASS |

The actual client-handler chain added the catalog iPhone at ?64,900, updated quantity to two, calculated ?1,29,800, verified persisted state and removed the item. No PostgreSQL products were modified. Sony MDR-EX15AP Black was ?829. A selected Samsung A16 at ?15,999 produced a strictly cheaper Samsung A06 at ?7,999. Comparison of ambiguous five-result context now asks which two; explicit first-two compares exactly two.

## Dynamic popup provenance

### Apple iPhone 15 ( Black,256GB )

HTTP 200; 22852.5 ms; cache miss; Ollama calls 1; Laya calls 0. Exact product context and model timing are preserved in the raw evidence.

1. Is this product suitable for heavy gaming due to its display and processor?
2. How does the camera compare to other smartphone cameras in its category?
3. Can I use this product with a non-Apple device, such as a Windows laptop?
4. What are the key differences between this product and other Android smartphones in its price range?

Sample review: four distinct, category-relevant questions. Compatibility and suitability questions ask for information; they do not prove those capabilities. Visible display is unverified.

### Samsung Galaxy A16 5G ( Blue Black, 6GB-128GB )

HTTP 200; 7958.6 ms; cache miss; Ollama calls 1; Laya calls 0. Exact product context and model timing are preserved in the raw evidence.

1. Is this 5G enabled phone suitable for a heavy gamer with a large screen?
2. Are there any alternatives to this phone with similar features and a lower price?
3. How does the camera quality compare to other mid-range smartphones in the market?
4. Is the 128GB internal storage sufficient for a user who stores a large collection of music and videos?

Sample review: four distinct, category-relevant questions. Compatibility and suitability questions ask for information; they do not prove those capabilities. Visible display is unverified.

### Samsung Galaxy Watch5 Pro LTE ( Gray Titanium,45 mm )

HTTP 200; 7597.9 ms; cache miss; Ollama calls 1; Laya calls 0. Exact product context and model timing are preserved in the raw evidence.

1. Is this smartwatch suitable for people with smaller wrists?
2. How does the built-in GPS compare to other smartwatches in this price range?
3. Can this smartwatch be used with both Android and iOS devices?
4. Are there any additional features or apps available for this smartwatch beyond what's included in the box?

Sample review: four distinct, category-relevant questions. Compatibility and suitability questions ask for information; they do not prove those capabilities. Visible display is unverified.

The clicked iPhone question traversed the actual Chatbot selection callback, Panel effect/send handler and live chat endpoint. Manual input then worked. Its generated answer correctly named the catalog A16 Bionic and six-core CPU (two performance/four efficiency cores). The adjective ?strong? is subjective; no benchmark or gaming suitability has been established.

## Controlled failure contracts

These tests used isolated FastAPI TestClient network-failure injections. Running services were not stopped, disabled or replaced. Full payloads and timings: [e2e-controlled-failures.json](e2e-controlled-failures.json).

| Case | HTTP | Result |
|---|---:|---|
| laya-timeout | 200 | PASS contract assertion |
| laya-malformed | 200 | PASS contract assertion |
| ollama-timeout | 503 | PASS contract assertion |
| ollama-connection | 503 | PASS contract assertion |
| ollama-empty | 503 | PASS contract assertion |
| suggestion-timeout | 504 | PASS contract assertion |
| suggestion-connection | 503 | PASS contract assertion |
| suggestion-malformed | 503 | PASS contract assertion |
| suggestion-empty-context | 422 | PASS contract assertion |

Laya failures produce an explicit `decision_service_error` with HTTP 200 under the existing contract, without invoking Ollama. This status remains a monitoring limitation. Greeting generation failures return 503; popup timeouts return 504 and malformed/connection failures 503, without static questions. Missing popup context returns 422.

## Confirmed defects and fixes

| Defect / root cause | Targeted change | Regression |
|---|---|---|
| Ambiguous comparison silently compared all recent products | chat_service.py clarifies which two, slices explicit first two | test_e2e_findings comparison case |
| Cheaper follow-up routed to details/cart or lost selection | chat_service.py strictly bounds selected category/price, preserves context on no result | selected/no-selection/no-result cheaper cases |
| Product-page selection lost after generated answer | chat_service.py persists resolved session context before generation | suggestion then manual-price case |
| Cart total with popup context sent to Ollama as product question | chat_service.py excludes cart requests from informational suggestion routing | cart-total-after-popup case |
| Processor evidence omitted and unprovided benefits encouraged | ollama_service.py retains chipset/CPU evidence and restricts prompt claims | processor-evidence case |
| Samsung suggestion asserted an unlisted office suite | ollama_service.py validates owned-feature clauses; suggestion_service.py bumps cache prompt revision | unsupported/actual/neutral-feature cases |
| Missing request-level intent/source/error diagnostics | routes/chat.py adds request ID/timing headers; ChatService records raw decision metadata and truthful source labels | existing provenance tests and live headers |

New regression file: `backend/test_e2e_findings.py` (nine tests). Original failed evidence is retained in e2e-live-before-fixes.json, e2e-live-intermediate.json and e2e-live-before-suggestion-guard.json, plus e2e-findings-before.log/e2e-cart-popup-before.log. Intermediate tests exposed weak semantic checks; assertions were tightened, not weakened. Editing the reload-enabled backend during one intermediate chain also reset process-local sessions; the final stable batch ran without source edits.

## Representative requests and responses

Search body: `{"message":"Show me Sony earphones under 1000 rupees"}`. The actual response lists catalog Sony MDR-EX15AP Black at ?829 with catalog stock/rating/discount. Full table and matching database row are in the live artifact.

Popup body uses the exact product `context` preserved in the artifact, including ID, name, category, price and specifications. Response shape is `{"suggestions":[...]}`. The questions above are actual response strings, not templates. Chat client messages include `<shopai_client_context>` for session/selection/cart; the runner reconstructs this using production handlers. No credentials are included in the evidence.

## Execution and browser evidence

Backend: 228 tests in 42.012 seconds, OK (`e2e-backend-full-suite.log`). A legacy intent-extraction test encountered an Ollama 20-second timeout and its legacy rules branch; this is not the production ChatService decision path. SQLite resource warnings remain in test teardown. Frontend: 44 tests passed (`e2e-frontend-tests.log`). Targeted runner lint passed (`e2e-changed-lint.log`); production build passed (`e2e-production-build.log`). Focused finding/suggestion tests: 26 passed. Controlled failures: nine passed.

Computer-use inventory returned `apps=[]`, `browsers=[]`; creating an in-app browser returned `Browser is not available: iab`. Native discovery returned `Computer Use native pipe is unavailable ... file not found (os error 2)`. No Playwright/Cypress configuration was found in the project. No screenshots or real UI claims are available.

## Remaining issues and reproduction

- Browser acceptance is incomplete: navigate to the three product IDs above once a browser provider is available, verify popup timing/location, switching/refresh, dismissal, controls, suggestion click and visible cart mutations.
- Generation latency remains substantial; the iPhone popup request took 22.85 seconds, including a measured 12.50-second Ollama model load. An intentional model unload was not performed. API timing does not measure browser paint.
- Photography recommendations are transparently rating-ranked in-stock catalog phones, not verified photography-performance rankings. Informational suitability answers are limited by available catalog evidence.
- Details currently present the first eight key specifications, not every catalog specification.
- Owned-feature lexical validation is bounded; it is not universal semantic hallucination detection. More live generations may expose unsupported qualitative language.
- Raw Laya intent predictions remain imperfect; deterministic validation corrects several tested requests. No classifier benchmark or scoring was changed.
- Session context is process-local and resets on backend reload. Laya service-error HTTP 200 semantics can obscure monitoring failures.

Run from the repository root in PowerShell:

```powershell
cd backend
../.venv/Scripts/python.exe -m unittest discover -s . -p "test_*.py"
../.venv/Scripts/python.exe scripts/validate_failure_contracts.py
cd ../frontend
node --test tests/*.test.cjs
npm.cmd run build
node tests/validate-e2e-live.cjs
```

The live runner requires unchanged running backend/frontend/Laya/Ollama/PostgreSQL services and writes fresh evidence; do not edit reload-watched backend code during its conversational chain. Failure injections are confined to their isolated test process. Independent model checks are recorded in e2e-model-inference.json. Existing routes, database schema, models and frontend design were preserved.

Independent live inference also passed: Laya product_search confidence 0.8949 (2,672 ms); Ollama greeting generation (12,144 ms). See [e2e-model-inference.json](e2e-model-inference.json).

## Browser-acceptance addendum â€” 10 October 2026

**Status: BLOCKED. No rendered browser acceptance was performed.** The API, client-handler, and isolated failure-contract results above remain the previously completed checks; they are not browser evidence. No popup visual, cart UI, or browser interaction is certified by this report.

### Environment inspection and blocker

- Frontend is React + Vite. `frontend/package.json` has no Playwright, Cypress, Puppeteer, or browser automation dependency, and `frontend/node_modules` has no matching installed package.
- Google Chrome and Microsoft Edge executables are installed. The computer-use provider inventory returned `apps=[]`, `browsers=[]`; binding a browser for `http://localhost:5173` returned `No browser is available`.
- No listeners were present on ports 5173 (Vite), 8000 (FastAPI), 5056 (Laya), 11434 (Ollama), or 5432 (PostgreSQL) when checked. Therefore this run could not verify service health or use the actual running storefront/API/model/database stack.
- No browser was launched and no automation dependency was installed. Consequently there are no screenshots, viewport observations, browser console/network logs, or measured frontend-to-paint timings to report. Product routes and desktop/mobile viewports were not tested.

### Acceptance matrix

| Browser scenario | Result | Evidence / limit |
|---|---|---|
| iPhone 15, Galaxy A16 5G, Watch5 Pro LTE routes and popup placement/timing | BLOCKED | No browser session or running services; no visual claim |
| Dynamic questions, product switching, cache isolation, loading/error display | BLOCKED | Existing live API samples remain in the earlier section; no rendered browser run |
| Dismissal, refresh, navigation, reopening, desktop/mobile overlap | BLOCKED | No browser interaction or screenshots |
| Chat open/close, greeting, query, suggestion click, follow-up, search/details | BLOCKED | Earlier handler/API evidence does not verify visible UI |
| Visible cart add, quantity/total, removal, persistence, product switching | BLOCKED | Earlier isolated client-handler evidence does not verify rendered cart |
| Browser console, failed requests, frontend trigger-to-paint latency | BLOCKED | Browser was not available |
| Cold/warm/cache-hit popup latency | BLOCKED for this browser run | Prior server API measurements are preserved above; no new request or cache-state experiment was run |
| Confirmed browser defects, fixes, regression tests | None established | No browser reproduction occurred; no code changes made |

### Reproduction when browser access and services are available

Start or connect to the existing PostgreSQL, Ollama, Laya V2, and FastAPI services without restarting healthy instances. Start the frontend from the repository root using `cd frontend; npm run dev -- --host 127.0.0.1`, then open the printed Vite URL in a browser exposed through the computer-use provider. Use actual catalog product routes/IDs from `e2e-catalog-snapshot.json` for iPhone 15, Galaxy A16 5G, and Watch5 Pro LTE. Capture desktop and mobile screenshots, browser console/network output, popup request timing headers, and visible cart state while following Phases 2â€“4 of the task instructions. Do not mark acceptance complete until those rendered checks are actually observed.

No application files or tests were changed in this addendum; the existing API and client-handler evidence remains distinct from browser acceptance.

## Recommendation popup correction â€” 10 October 2026

**API/generation path: verified with final source. Rendered browser acceptance: still BLOCKED.** No browser screenshots, DOM interactions, or browser paint measurements were produced in this correction.

### Source trace and confirmed root cause

The popup renders only the validated strings returned by `getProductSuggestions` â†’ `api.getChatSuggestions` â†’ `POST /api/chat/suggestions` â†’ `generate_suggestions` â†’ `OllamaService.generate_suggestions`. The endpoint calls the configured `llama3.2:latest` model and parses its JSON into `SuggestionResponse`. The old popup flow had no hardcoded recommendation array, question template, static fallback, or localStorage suggestion source; failures rendered no questions. React Query held successful data for five minutes, keyed by the old product/listing context.

The confirmed Mobiles listing defect was context loss: `getProductSuggestionContext(search)` sent only `{name: "Mobiles", category: "Mobiles"}` and omitted the visible catalog results and active filters. Ollama was asked a generic catalog question, which explains the generic listing questions. Product pages already supplied product information, but the frontend cache key used the product ID only, so a changed price/specification could reuse old output. Generation output could also ignore listing wording or invent numeric details; backend numeric validation already rejected unsupported numbers, but the UI had no loading/retry presentation while generation or rejection was in progress.

### Changes made

- The root now owns a shared listing context so the chatbot sibling can observe the products page. The route publishes its actual filtered result slice and active filters after its catalog query succeeds, and clears that context on query error or route exit. Empty listings do not trigger suggestion generation.
- Category/listing payloads include the current category/query, filters, and up to eight current result rows with catalog IDs, names, brands, categories, prices, and available specs. Product payloads now include the exact selected product ID/name/category/price and supplied description/specifications.
- Listing and product prompts have separate instructions. Listing output is asked to discuss the category/options/results and not refer to one item as â€œthis productâ€. A backend guard rejects listing questions that nevertheless use singular-item wording. Existing schema, numeric, duplicate, and selected unsupported-feature validation remains in force; rejected model output is not cached or displayed.
- The React Query key now includes the serialized full generation payload, prompt revision, and model configuration. Backend cache identity already includes the full payload and model config; prompt revision is `questions-v8`. The successful-result TTL remains five minutes. Context changes create a new query and the old request receives React Queryâ€™s abort signal, so stale results stay attached to the old key.
- The popup shows a loading status while generation is pending and a clear retry action after errors. It still displays only generated, validated strings. React Query deduplicates identical in-flight requests; retry is explicit and no fallback is added.
- Existing request IDs and timing headers/logs now report Ollama load, prompt evaluation, generation/server total, backend API processing, validation, and frontend request/receive/render events. No model, Laya, API contract, database, or storefront design was replaced.

### Regression and build results

- Backend: `cd backend; ..\\.venv\\Scripts\\python.exe -m unittest test_suggestion_lifecycle test_suggestions` â€” **21 tests passed**. Coverage includes product/listing context separation, generation-service provenance, cache context/config separation, single-flight behavior, malformed output rejection, unsupported numeric/causal claims, and no fallback.
- Frontend: `cd frontend; node --test tests/product-suggestions.test.cjs tests/suggestion-transport.test.cjs tests/proactive-popup.test.cjs tests/suggestion-click.test.cjs` â€” **28 tests passed**. Coverage includes actual category result/filter payload construction, context-sensitive query identity, cancellation on navigation, deduplication, loading/error/retry states, and existing click/chat behavior.
- Production build: `cd frontend; npm.cmd run build` â€” **passed**.
- The Node popup timer test measured about **1.25 seconds** from context to test-render eligibility. This is not a browser paint measurement.

### Final-source live suggestion API evidence

These requests used FastAPI `TestClient` against the actual `/api/chat/suggestions` route and the configured Ollama server/model. The Ollama call was real; the FastAPI route was exercised in-process rather than through a running Uvicorn listener. Requests used unique IDs and were cache misses. This is API evidence, not rendered browser acceptance.

Exact generated strings, request IDs, status codes, and timing fields are preserved in [popup-recommendation-live-results-2026-10-10.json](popup-recommendation-live-results-2026-10-10.json).

| Context | HTTP | Ollama calls | Backend API ms | Ollama wall ms | Model load ms | Prompt eval ms | Server total ms | Outcome |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Apple iPhone 15 (Black, 256GB), supplied chip/storage/color context | 200 | 1 | 4,889.2 | 4,868.0 | 22.1 | 765.1 | 2,828.6 | Four generated questions; cache miss |
| Samsung Galaxy A16 5G, supplied network/storage context | 200 | 1 | 2,446.0 | 2,444.0 | 20.8 | 480.6 | 2,440.7 | Four generated questions; cache miss |
| Mobiles listing with two actual catalog-shaped result rows | 200 | 1 | 3,186.2 | 3,182.8 | 19.9 | 757.7 | 3,178.0 | Three generated category/listing questions; cache miss |

The measured repeat iPhone request was a **cache hit**: HTTP 200, no Ollama call, and 1.645 ms backend API time. Earlier live attempts also demonstrated the failure contract: unsupported numeric outputs (for example an invented â‚¹20,000 threshold or unsupported count) returned HTTP 503 with no suggestions, and the UI retry state covers that response.

Model loading was only about 20 ms in the final batch, so it was not the main latency source; intentionally unloading the model to manufacture a cold start was not done. Ollama server totals were about 2.44â€“3.18 seconds, while HTTP wall time ranged from about 2.44â€“4.87 seconds. The iPhone request had about two seconds between Ollama wall and server total, so transport/runtime overhead plus prompt evaluation and token generation dominate more than model loading. Backend validation took under 5 ms in the recorded successes. Frontend request-to-visible timing remains unmeasured in a real browser.

### Remaining limitations and acceptance state

- The final source and API path are verified, but popup placement, loading visibility, click behavior in the DOM, mobile overlap, navigation/refresh, browser console/network errors, and visible cart state remain **BLOCKED** because the browser provider previously returned no available browser session. The Vite/frontend and FastAPI listener ports were not available during the earlier browser inspection.
- Ollama remains nondeterministic. Some live generations were rejected for unsupported numbers or singular listing phrasing; they were not cached or displayed. The retry state makes this visible, but the lexical validator is not universal semantic hallucination detection.
- The final API batch used a representative Mobiles listing payload with two catalog-shaped results; it did not load the actual storefront in a browser or measure the live pageâ€™s filter/query propagation end to end.

To reproduce the focused checks, run the backend/frontend commands above. For live generation, keep the configured Ollama service reachable and call `POST /api/chat/suggestions` with (a) an iPhone context, (b) a Samsung context, and (c) `{name: "Mobiles", category: "Mobiles", products: [...]}` from actual current listing results; retain each `X-ShopAI-Request-ID` and `X-ShopAI-Suggestion-Timing` header. Browser acceptance requires an available browser provider and running storefront/API stack; use the earlier browser addendumâ€™s desktop/mobile route checklist before marking visual acceptance complete.

## Cart-removal follow-up - 10 October 2026

**Code-path defect reproduced; screenshot cart membership remains unverified.** The user-reported screenshot did not include a machine-readable cart snapshot in the workspace. The saved `cart-total-live-results.json` is a different test run and does not contain the reported â‚¹75,055 / six-item state. At inspection time, no browser session was available and no frontend, FastAPI, Laya, Ollama, or PostgreSQL listener was running. Therefore the Sony MDR-EX15AP item cannot be confirmed as present or absent from those six items; a product search result is not cart evidence.

### State flow and root cause

`CartProvider` stores `{product, quantity}` entries in `shopai_cart_items` and derives item count and subtotal from those entries. `ChatbotPanel` reads its latest render's cart ref for each `/api/chat` request and sends every item's actual `id`, `name`, `price`, and `quantity` in `<shopai_client_context>`. The session wrapper replaces its stored cart with that request's cart snapshot; it removes the cart field when a request supplies none. `Show me my cart` and cart totals format only that current client snapshot.

The removal resolver first tried literal canonical-name inclusion, then required every reference token to occur exactly in the catalog-name tokens. The catalog record for the requested Sony item is `Sony MDR-EX15AP Earphone ( Black )`, while the reported text says â€œSony MDR-EX15AP earphonesâ€. The singular/plural difference prevented an otherwise strong name match, and the resolver returned a generic â€œisn't in your cartâ€ message without listing the actual cart. That is a confirmed false-negative path when this product is present under its canonical singular name. The exact screenshot membership remains unknown.

### Change and regression coverage

- Cart removal now resolves an exact current cart product ID first, then matches normalized tokens against each current cart line's canonical display name. Conservative plural normalization handles `earphones` / `earphone`; matching never searches outside the submitted cart.
- If a named item is absent, the response now says it is absent and lists the exact current cart names, IDs, quantities, prices, and total. No cart mutation marker is emitted.
- Existing client handling remains the sole mutation path. It validates the current item ID and expected quantity, applies removal/update to `CartProvider`, and formats success only after the state operation; cart state then persists to localStorage. Each later message sends the newly rendered cart snapshot.
- Added backend regressions cover the Sony plural-name case with its catalog ID/name, absent Sony plus actual-cart listing, quantity/total changes, subsequent cart display, and session snapshot replacement. Existing frontend cart-handler tests cover mutation execution, total/count recomputation, persistence, stale quantity rejection, and no false success.

Focused validation: backend `test_cart_quantity_language` and `test_chat_regressions` passed (52 tests, including the session-snapshot regression). Frontend `node --test tests/chat-cart.test.cjs` passed (18 tests). These are deterministic unit/handler checks, not a live service endpoint or rendered browser check. No source behavior was validated against the screenshot's actual six cart lines or browser localStorage.

To finish the screenshot-specific verification, provide the six cart rows (product ID/name, quantity, and unit price) or make the original browser/cart session and services available. Then repeat the remove request and verify the visible cart count and total after the client handler runs. Until then, Sony's presence in that reported cart and rendered UI behavior remain unverified.

## Mobiles suggestion failure follow-up - 10 October 2026

**Failure reproduced against configured Ollama; browser acceptance unavailable; dynamic generation remains blocked by host memory.** The screenshot contained no request ID or network trace. I reconstructed the current default Mobiles context from the saved 508-row catalog snapshot: default `maxPrice=150000`, no stock/brand/rating/discount restriction, page 1, and the first eight rows in default catalog order. Ninety rows met the price/category filter. The 8-row request was 2,291 bytes and passed `SuggestionRequest` validation. This is a catalog-backed API reproduction, not proof that the screenshot had the same browser rows and filters.

Evidence is preserved in [popup-mobiles-failure-2026-10-10.json](popup-mobiles-failure-2026-10-10.json). Request ID `mobiles-screenshot-repro-321aa13ae0` returned HTTP 503 with `{"detail":"Suggestions are unavailable (model_connection_or_service_failure)."}`. Backend duration was 4,311.85 ms; the single Ollama attempt took 4,303.701 ms. Laya calls were zero and the cache missed. Ollama `/api/tags` returned 200 and showed `llama3.2:latest` installed; `/api/ps` showed no loaded model. Ollama `/api/chat` returned HTTP 500: `llama-server ... failed to allocate buffer of size 649046272 ... unable to allocate CPU buffer`. A separate default GPU startup check failed `cudaMalloc` allocating 2,011,539,712 bytes. A CPU-only check failed the same 649 MB allocation. No model output was returned, so output parsing, question-count validation, and semantic validation were not reached. This was not a request-context/schema error, validation rejection, timeout, or Laya failure.

The popup already had concise error copy and its Retry action called React Query `refetch`. I fixed a confirmed stale-data rendering defect: cached questions could still be mapped when that query was in an error state. Failed queries now show no suggestions; the Retry control disables and changes label while fetching. Developer logs now include the Ollama provider status, bounded provider error body, traceback, request ID, and timing fields. The public error remains concise.

Regression results: backend `test_suggestion_lifecycle` passed **11 tests** before the final test-fixture edit added the explicit default `maxPrice` field. The rerun then failed before test discovery with Python `MemoryError` during SQLAlchemy import. Frontend focused tests (`proactive-popup`, `product-suggestions`, `suggestion-transport`) passed **25 tests**. The production build did not pass: Vite/Node terminated with `Fatal process out of memory: Zone`.

The live route reproduction used FastAPI TestClient but made a real HTTP call to Ollama. No suggestions could be verified because the model runner could not allocate memory. The Node/browser provider inventory returned `apps=[]`, `browsers=[]`; no rendered popup or browser Retry click was observed. Free CPU/GPU memory or use a host with sufficient available memory, then repeat the live category request and production build. The screenshot's exact browser payload remains unavailable.

## Dynamic suggestion latency optimization — 10 October 2026

**Verified: live suggestion API and Ollama generation. Browser paint timing remains unverified.** The earlier Mobiles memory failure was not present during this run: the configured Ollama endpoint was reachable and returned generated output. No model, Laya V2, or Ollama service was disabled. The suggestion endpoint continues to call Ollama directly; it does not route suggestion generation through Laya.

### Baseline and measured bottleneck

Before editing code, I inspected the popup, API route, service, and Ollama request, then called the real FastAPI suggestion route with the configured `llama3.2:latest` service. Baseline payloads used the saved 508-row catalog snapshot for an iPhone 15, Galaxy A16, and filtered Samsung Mobiles listing. Full request IDs, question text, context sizes, Ollama substage timings, output, and responses are in [popup-performance-before-2026-10-10.json](popup-performance-before-2026-10-10.json).

Warm baseline misses took 6.33 s for the Galaxy A16 and 11.33 s for the filtered Mobiles listing. Their reported model loads were only 15.9 ms and 12.7 ms. The A16 spent 3.70 s in prompt evaluation and 2.51 s generating; the listing spent 5.01 s evaluating and 6.20 s generating. Backend response parsing/validation was below 0.5 ms. This shows inference, especially prompt evaluation and token generation, dominated warm requests; model loading was not the warm-request bottleneck. The initial iPhone request took 20.89 s and reported a 10.19 s model load plus 6.64 s prompt evaluation. Although `/api/ps` had shown the model loaded at the initial environment check, that measurement cannot certify a fully cold start. No model unload was forced.

The measured baseline product request had 1,868 system-prompt characters and 2,670 context characters for the iPhone; the Samsung request had 1,868 and 1,887. The listing prompt/context measured 784 and 2,010 characters. Before this change, prompt construction, JSON parsing, and frontend trigger-to-request did not have separate numeric timers in the saved baseline.

### Changes

- Replaced repeated prompt instructions with a short product/listing-specific instruction and retained factual, listing-singular, numeric, schema, duplicate, and owned-feature validation.
- Kept the full client context in the cache identity and factual checks. For model input only, product pages retain exact name, brand, category, price, a distinct short description when present, and up to eight specifications ranked by relevant field names and value length. Listing requests retain current category/query/filters and up to five real visible results with names, brands, categories, prices, and up to two salient specifications each.
- Asked Ollama for a JSON array constrained by the existing 3–4 item, string-length, and question-mark schema. The HTTP response remains the existing `{ "suggestions": [...] }` shape. Output generation is capped at 128 tokens with a 2,048-token context; temperature remains 0.4. The configured model and shared `requests.Session` are unchanged.
- Added separate timings for prompt construction/size, prompt-evaluation and output token counts, JSON parsing, semantic validation, Ollama load/evaluation/generation/server total, and overall API processing. Cache keys now use prompt revision `questions-v10`; the existing context-sensitive successful-result cache, React Query deduplication/cancellation, and backend single-flight behavior remain.
- Removed the artificial 1.2-second popup display timer. The existing loading state now becomes eligible as soon as the current product/listing context and capability check allow the suggestion query. The component layout, retry control, and chat selection handler remain in place. A failed output is still hidden and not cached.

### Live API results after the change

These are HTTP calls through FastAPI `TestClient` to the actual suggestion route, which made real requests to the configured Ollama service/model. PostgreSQL initialized with its 508-row catalog; category context was built from actual matching catalog rows and Samsung/price filters. These are API measurements, not requests through a running Uvicorn listener or a rendered browser. Request IDs and full outputs are preserved in [popup-performance-after-2026-10-10.json](popup-performance-after-2026-10-10.json).

| Context / cache state | HTTP | Questions / relevance and checks | API wall / backend ms | Ollama wall ms | Load / prompt eval / generation ms |
|---|---:|---|---:|---:|---:|
| Apple iPhone 15, warm miss | 200 | 4; display, camera, and battery; no exact duplicates; validation pass | 4,392 / 4,379 | 4,375 | 43 / 1,192 / 1,033 |
| Samsung Galaxy A16 5G, warm miss | 200 | 4; connectivity and product-use questions; no exact duplicates; validation pass | 800 / 798 | 796 | 12 / 18 / 715 |
| Mobiles, Samsung and ₹5,000–₹20,000 filters, warm miss | 200 | 4; color/connectivity options plus an A16/4GB cross-variant question; no exact duplicates; validation pass, with limitation below | 3,543 / 3,541 | 3,539 | 13 / 2,186 / 1,307 |
| Same filtered Mobiles context, cache hit | 200 | Same 4 validated questions | 2.71 / 0.853 | 0, no Ollama call | — |

| Context | Prompt build ms | Prompt/context chars | Ollama prompt/output tokens | JSON parse / validation ms |
|---|---:|---:|---:|---:|
| Apple iPhone 15 | 0.716 | 900 / 576 | 267 / 56 | 0.004 / 0.793 |
| Samsung Galaxy A16 5G | 0.431 | 758 / 434 | 245 / 40 | 0.004 / 0.288 |
| Filtered Mobiles listing | 0.323 | 1,605 / 1,134 | 487 / 71 | 0.004 / 0.608 |
| Same listing cache hit | — | — | — | — |

Every uncached response contained four different question strings. The product outputs used supplied camera/display, connectivity, or other product context; the listing output mostly referenced visible colors and connectivity, with the A16/4GB cross-variant question noted above. Exact duplicate detection passed and all three misses passed the existing schema/numeric/claim checks. The category repeat returned the same validated questions from cache. These checks do not prove every question-to-product association: the listing sample asked whether the Galaxy A16 5G has a 4GB RAM variant, while the supplied rows showed 6GB/8GB A16 variants and a 4GB A06. That was phrased as a question, not a claim, but its answer is not established by those rows. The lexical validator does not fully detect cross-product feature mixing. One earlier `questions-v9` listing attempt generated an unsupported ₹15,000 amount; the unchanged numeric validator rejected it, returned no questions, and did not cache it. Listing wording was tightened in revision v10; the final run passed while this semantic-association limitation remains. No validation rule was removed.

Against the pre-change warm Galaxy A16 run, elapsed time fell from 6.33 s to 0.80 s (87% lower); prompt/context characters fell from 3,755/1,887 to 758/434. For the same filtered listing shape, time fell from 11.33 s to 3.54 s (69% lower), and prompt/context characters fell from 2,794/2,010 to 1,605/1,134. The iPhone final warm run was 4.39 s versus 5.20 s in the earlier verified warm iPhone sample; its prompt/context fell from 4,538/2,670 in the immediately preceding baseline to 900/576. These are individual local runs, not a statistically controlled latency benchmark; Ollama timing varied between consecutive prompts. The successful same-context cache hit remained about 2–3 ms.

### Frontend timing and verification limits

The browser code records `context_available`, `frontend_request_started`, `frontend_received`, and a post-render animation-frame visibility event. The Node component harness observed context-to-render in about 0.1 ms after the display timer was removed. That harness does not measure an actual browser request, DOM paint, layout, or visible popup. No rendered browser run was performed, so frontend trigger-to-API and response-to-paint values remain unavailable; the 4.39/0.80/3.54-second values above are API/Ollama times only. The loaded-model misses reported 12–43 ms load time. A controlled unloaded-model cold start was not performed; the earlier first-request 10.19 s load duration is retained as an observation, not certified cold latency.

Focused verification: backend `test_suggestions` and `test_suggestion_lifecycle` passed **22 tests**; frontend `product-suggestions`, `suggestion-transport`, `proactive-popup`, and `suggestion-click` passed **29 tests**; `npm.cmd run build` passed. The popup is faster in the measured warm API samples, with the strongest matched-context reductions shown above. Rendered browser placement, browser-network timing, and actual frontend-to-paint performance remain unverified.

## Listing fact association follow-up — 10 October 2026

**API path: verified. Browser rendering: not tested.** The saved `popup-performance-after-2026-10-10.json` evidence contains the reproduced cross-row defect: the Samsung Galaxy A06 listing row was `4GB-64GB`, while Galaxy A16 rows were `6GB-128GB` or `8GB-128GB`. The generated question “Are the Samsung Galaxy A16 5G models available in a 4GB RAM variant?” passed the prior global number check because `4GB` appeared somewhere in the full listing. That was the confirmed root cause; the question was interrogative, but still attached a catalog value to the wrong model.

The listing validator now extracts explicit model codes from each product row and from each generated question, associates measurable values (including GB/TB, capacity, camera, display, network, and currency values) with the nearest named code, and checks for the value within rows of that exact model. The check is applied to all generated questions regardless of whether the wording is an assertion or a question. This rejects both “Are the A16 models available in a 4GB RAM variant?” and “Does Galaxy A16 have 4GB of RAM?” even though A06 has 4GB. A correctly named A06 4GB question remains supported. Failed product-value associations trigger at most one fresh Ollama generation with corrective context. If that also fails validation, the route returns its existing concise error response; it does not cache or show invalid output, and the popup retry action remains unchanged. The model and API response schema are unchanged. Prompt/cache configuration revision advanced from `questions-v10` to `questions-v11`, so old generated values cannot bypass the stricter validator.

Validation is bounded: it grounds explicit numeric/unit/currency facts to named model rows and retains the existing numeric and selected unsupported-feature checks. It does not parse every possible natural-language compatibility, quality, or feature claim into a formal catalog predicate; ambiguous naming, nonnumeric paraphrases, and unsupported qualitative implications may need stronger semantic validation. This does not solve all hallucinations.

### Verification

- Backend focused suites: `test_suggestions` and `test_suggestion_lifecycle` — **24 tests passed**. New regressions cover A06/A16 RAM transfer in interrogative wording, regeneration to valid model output, bounded retry exhaustion, no static fallback, and a validation-time budget.
- Frontend suite: `node --test tests/*.test.cjs` — **47 tests passed**. Existing retry/current-context, stale-response, cache identity, and popup output tests remain green.
- Production build: `npm.cmd run build` — **passed**.
- Live API: request ID `semantic-grounding-mobiles-live`, actual filtered Mobiles context from the saved performance payload, HTTP 200, two real Ollama calls (one corrective retry), four generated questions, successful validation. The initial model output failed an existing unsupported-number check and was withheld. Final response and timing fields are in [popup-semantic-grounding-2026-10-10.json](popup-semantic-grounding-2026-10-10.json).

### Added validation cost and latency

Across the live two-attempt request, association validation took **1.699 ms** and all parsing/validation took **2.976 ms**. Backend API time was **7,992.725 ms**, with the two Ollama calls accounting for **7,989.09 ms**. The last Ollama attempt reported 22.8 ms model load, 346.7 ms prompt evaluation, and 1,179.9 ms generation; the first attempt also incurred inference time before rejection. Validation itself is small; the extra latency came from regenerating after the initial rejection. Single-attempt association validation is also covered by the unit test's under-20 ms budget. These are API timings, not frontend rendering or browser paint measurements.

The live output had separate A06/A16 questions and made no A16/4GB claim. It did ask about expandable storage for A06 although the compact listing rows do not supply an A06 storage-expansion specification. This shows the remaining limitation: the new check catches explicit measured values misattributed across models, but cannot establish every nonnumeric capability from compact listing data. Browser acceptance remains unverified.

## Recommendation arrival speed follow-up — 10 October 2026

**Measured result: request initiation is no longer gated on capabilities, but uncached API latency did not show a reliable median improvement. Visible browser arrival remains unmeasured.**

### Baseline and bottleneck

Before editing, I measured three uncached requests each for Apple iPhone 15, Samsung Galaxy A16 5G, and the filtered seven-row Samsung Mobiles listing, followed by a cache hit for each. Requests used the actual saved product/listing contexts and live configured Ollama through FastAPI `TestClient`; model was already warm. This is a cold-cache/warm-model baseline, not a cold model load. Full request IDs, outputs, API timings, and samples are in [popup-arrival-baseline-v11-2026-10-10.json](popup-arrival-baseline-v11-2026-10-10.json).

The main cost is Ollama inference. Backend cache lookup in the later v13 timing samples was around 0.01–0.04 ms; baseline parsing/validation was 0.35–4.37 ms, and API processing outside Ollama was only a few milliseconds. A rejected output adds a second Ollama call and can multiply response time; the A16 and listing baselines each had a two-call sample. Ollama warm generation varied substantially between adjacent requests. The frontend also waited for `/api/chat/suggestion-capabilities` before enabling its suggestion query, putting that request on the context-to-generation critical path. No browser timing was available to measure the actual size of that wait.

### Changes

- `ProductSuggestionPopup` now starts the capabilities query as soon as the root popup component mounts and lets the suggestion query start when valid product/listing context is ready, without waiting for the capabilities response. The endpoint still reports disabled-provider errors; returned capabilities can hide a disabled popup. Model-configuration changes invalidate the context-keyed React Query suggestions. The full context and prompt revision remain in the key, and backend successful-result caching and single-flight behavior remain active.
- The generator requests exactly four concise questions (at most 12 words each) in the JSON schema and lowers `num_predict` from 128 to 96. Product/listing context compaction, `llama3.2:latest`, shared HTTP session, factual validation, and one-retry limit remain. The listing prompt names the singular phrases rejected by validation; a listing wording rejection can use the same single bounded regeneration. Prompt/cache revision advanced from `questions-v11` to `questions-v13` to invalidate output from the previous prompt instructions.
- Backend timing now records cache lookup duration and individual Ollama attempt wall/load/prompt-evaluation/generation/server times; frontend diagnostics record context-ready-to-request-start.

### Before and after samples

Each row is three cache misses (median and nearest-rank p95; with only three samples p95 is the maximum and is descriptive, not a stable percentile estimate). The model was already warm in both batches. The after Mobiles batch had two successes and one retry-exhausted HTTP 503; its all-request latency distribution includes that failed request. Cache hits are separate.

| Context | v11 miss median / p95 ms | v13 miss median / p95 ms | v13 successful outputs |
|---|---:|---:|---|
| iPhone 15 | 1,160 / 4,802 | 1,348 / 4,005 | 3 of 3 HTTP 200, one Ollama call each |
| Galaxy A16 5G | 1,169 / 4,554 | 1,684 / 4,157 | 3 of 3 HTTP 200; one request needed the allowed retry |
| Filtered Samsung Mobiles | 1,596 / 6,881 | 2,211 / 6,471 | 2 of 3 HTTP 200; one retry exhausted on unsupported A06/5G association |

The v13 cache hits were 7.0 ms, 8.8 ms, and 10.4 ms end-to-end in `TestClient`; backend cache lookup itself was about 0.01 ms and Ollama call count was zero. Before hits were 5.1–6.6 ms. The added lookup/attempt diagnostics and local request variation are within this small range. The final v13 API results and per-attempt timings are in [popup-arrival-after-v13-2026-10-10.json](popup-arrival-after-v13-2026-10-10.json).

Across these samples, p95 maxima were 6–17% lower after tuning, but medians were 16–44% higher. Output token counts fell in these small samples, while actual generation time remained noisy; therefore these measurements do **not** prove a consistent uncached API speedup. The 96-token cap was not reached by successful outputs (maximum observed output was 69 tokens), so it is a safety bound rather than a demonstrated latency lever. The measurable arrival-path change is that capabilities no longer has to complete before the suggestion request is enabled. This was verified by the frontend harness with capabilities still pending, not timed in a real browser.

### Context quality and verification

Live API samples covered the iPhone 15, Galaxy A16 5G, and filtered Mobiles listing with its actual A06/A16 variants. Successful outputs contained exactly four distinct questions and passed schema and current factual validation. The supported A06 4GB/A16 6GB-or-8GB regressions, misattributed RAM/price rejection, bounded regeneration, exhaustion/no-cache failure path, and cache timing pass the focused backend tests. One live Mobiles request generated a 5G value associated with A06 twice; after the single retry, the endpoint correctly returned HTTP 503 and no suggestions. That is a quality failure surfaced through the existing retry UI, not a valid suggestion.

- Backend focused suites: **24 passed** (`test_suggestions`, `test_suggestion_lifecycle`).
- Frontend suite: **49 passed** (`node --test tests/*.test.cjs`), including capabilities prefetch and suggestion-query start while capabilities are pending, stale-context cancellation, and error/retry behavior.
- Production build: `npm.cmd run build` — **passed**.
- The computer-use provider could not start its native pipe (`file not found`, OS error 2). No browser was available for DOM, network, popup-paint, or response-to-visible timing. The Node harness previously observed about 0.2 ms for a synthetic context-to-render path; this is not browser paint. Cold-model timing was not measured or forced.

Current limits: warm Ollama inference and the occasional necessary retry dominate arrival time. The capability prefetch removes a serial dependency in the frontend code path, but the amount saved on the user's browser remains unknown. No reliable overall arrival-speed improvement or faster visible popup is claimed from these measurements.

