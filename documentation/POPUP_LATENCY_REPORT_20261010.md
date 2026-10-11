# Product suggestion popup and latency — 2026-10-10

## Outcome and remaining acceptance work

Targeted lifecycle, diagnostic, cancellation and successful-output caching changes are implemented and tested. The exact iPhone 15 product and a real Samsung watch returned genuine model-generated questions through the running backend. **Rendered browser verification remains incomplete, and the 2–3 second visible-popup target is not verified.** Fresh inference exceeded that target. Cached HTTP responses are fast; they are not browser paint measurements.

Browser automation was attempted through the available CUA inventory, in-app browser creation and the documented native computer-use helper. Inventory returned no apps/browsers, in-app creation returned `Browser is not available: iab`, and the native helper returned `Computer Use native pipe is unavailable ... The system cannot find the file specified (os error 2)`. No screenshot or browser navigation result is claimed. Neither model was unloaded to manufacture a cold-start measurement.

## Root causes and full lifecycle

The iPhone route and API ID `apple-iphone-15-black-256gb` are valid. Its product API returned real catalog context. `Chatbot` already mounts `ProductSuggestionPopup`; the product page and popup use the same `['product', productId]` query key. The popup was not excluded by an incorrect product ID or a missing mount in the inspected implementation.

The live failure occurs downstream: Ollama sometimes takes tens of seconds and sometimes produces questions rejected by the response/numeric-fact validators. The original endpoint returned a generic 503 for invalid output and the frontend correctly returned no popup. For the exact iPhone context, a request succeeded after 31.657 seconds, the next failed after 3.711 seconds, and another pre-change request failed after 6.854 seconds. The old code provided no useful request correlation or reason in the response.

Across products, uncached prompts, prompt evaluation time and model-output validation differ. On the final warm watch run, prompt evaluation alone took 4.538 seconds, versus 0.264 seconds for the iPhone. Generation took about 3 seconds in each case. This explains why a fixed 1.2-second UI timer cannot guarantee a popup within 2–3 seconds.

The old frontend timing effect was also misleading: `visible` depended only on the timer/dismissal state, so it recorded a visibility event even while the component returned null waiting for model output. It now requires actual validated suggestions and enabled capabilities before scheduling the two animation-frame paint observation. This measurement is installed but has not been observed in a real browser in this task.

Current flow:

1. Product query supplies the current catalog product; ID equality and valid name/price are required.
2. Context availability is recorded with `performance.now()`. A lightweight capability endpoint reports whether Ollama is enabled and returns a model configuration fingerprint without querying PostgreSQL or calling Laya.
3. React Query requests suggestions once per product ID, full context and model fingerprint. It supplies its cancellation signal; navigation cancels the abandoned fetch. The 1.2-second display delay runs concurrently with generation.
4. Backend validates the context, checks configuration and looks up a five-minute cache keyed by full context (including product ID), Ollama URL/model/credential fingerprint and prompt revision. A single-flight Future shares identical concurrent work. Only validated genuine output is cached, with a maximum of 128 successful entries and 128 distinct active generations.
5. On a miss, the existing shared HTTP session calls the configured Ollama model using unchanged generation settings. Laya is not required and is not called in this path.
6. Backend exposes request ID, monotonic processing durations, model load/prompt/generation durations, cache status, operation counts and failure reason in response headers and structured logs. Failures are not cached. Invalid output/connection failure returns 503; timeout returns 504.
7. Frontend validates the returned question strings and records loading, success, timeout, cancellation, disabled and failure events. It renders only genuine output for the current query/context. The popup remains portaled to the body with fixed `z-50`, viewport bounds and overflow scrolling. Dismissal remains per product/search context for the mounted storefront session; dismissed contexts stop further requests.

No model checkpoint, temperature, context-window size or generation-token limit was changed. The prompt now favors relevant questions without unnecessary numerical restatement, reducing opportunities to invent numeric facts. Invalid output still stays hidden; probabilistic generation cannot guarantee every uncached request will pass validation. Backend inference may continue to its bounded timeout after a browser cancels its HTTP fetch; it is not forcibly terminated.

## Actual measurements

All times below are milliseconds, measured from HTTP requests and backend monotonic timers. “First” means the first request in that batch, **not proven cold inference**. Models were already in use. Confirmed model load durations in the final batch were only 14.9 and 19.7 ms.

| Product | Before first request | Before subsequent request | After fresh warm generation | After cache hits |
|---|---:|---:|---:|---:|
| iPhone 15 Black 256GB | 31,656.6 success | 3,710.9 invalid output | 5,196.7 success | 4.4, 17.8 |
| Samsung Watch5 Pro LTE Gray Titanium | 8,020 success | 3,887 success | 7,713.2 success | 4.7, 4.4 |

Additional pre-change iPhone requests were 6,854 ms (invalid) and 4,454 ms (success). The initial probe used an incorrect guessed watch slug and recorded its 404; the valid catalog ID was then discovered and measured rather than silently omitting the category.

Final per-stage evidence (`popup-latency-after-verified.json`):

| Stage | iPhone fresh | Watch fresh |
|---|---:|---:|
| Product HTTP fetch / context acquisition | 2,094.2 | 5.6 |
| Suggestion HTTP round trip | 5,196.7 | 7,713.2 |
| Backend processing | 5,191.2 | 7,709.6 |
| Laya calls / duration | 0 / 0 | 0 / 0 |
| Ollama HTTP duration | 5,187.8 | 7,707.8 |
| Ollama reported model load | 14.9 | 19.7 |
| Ollama reported prompt evaluation | 263.7 | 4,537.7 |
| Ollama reported generation | 2,873.7 | 3,033.4 |
| Ollama reported server total | 3,163.1 | 7,705.0 |
| Output validation | 0.638 | 0.271 |
| Browser context-to-request / paint | unavailable | unavailable |

Cached backend processing was 1.2–1.8 ms, with zero Ollama and zero Laya calls. Product acquisition times are not included in suggestion HTTP times, and model substage times overlap the Ollama HTTP duration rather than adding to it. No frontend/backend clock subtraction is used. A Node component harness measured the existing delay at 1,251.1 ms; that is not a browser paint or an end-to-end model measurement.

The final batch had **6 requests, 6 successes, 0 failures and 0 timeouts**. Earlier post-change exploratory measurements included one rejected watch output; that failure is retained in `popup-latency-after.json`. Across the two pre-change batches there were six suggestion requests with two rejected outputs and zero timeouts, plus the recorded invalid-slug 404. Tests separately exercise actual timeout/connection exceptions and frontend abort behavior. True unloaded-model cold latency and visible warm latency remain unmeasured. The **2–3 second target was not achieved for fresh warm HTTP generation and is not claimed for browser display**.

## Verification

- **211 backend tests passed**: suggestion API/cache/single-flight/configuration/expiry/disabled-state/timeout/connection checks, greetings, Laya contracts, product search, follow-ups, concurrency, comparison, provenance and cart regressions. `popup-backend-regressions.log` retains the result and existing SQLite fixture resource warnings.
- **44 frontend tests passed**: exact iPhone context, watch navigation without remount, slow model output, truthful paint timing, dismissal/revisit, real React Query cancellation and duplicate prevention, abandoned stale responses, timeout, invalid context/output, connection failure and existing cart/chat handlers. `popup-frontend-tests.log`.
- Changed frontend production files and the three touched/new popup test files passed ESLint (`popup-changed-lint.log`, empty on success). No Python lint tool/config is present in the repository; backend syntax/imports are exercised by the tests.
- Final production `npm run build` passed (`popup-production-build.log`).
- Both approved Laya V2 and Ollama independently passed live inference (`popup-model-live-results.json`). Actual suggestions use only Ollama, and the six final HTTP requests confirm zero Laya calls in that path.
- No real browser test or screenshot was executed successfully. Responsive layout/stacking are structurally tested but remain a visual acceptance gap.

## Files changed in this task

- `frontend/src/components/storefront/ProductSuggestionPopup.tsx`
- `frontend/src/lib/product-suggestions.ts`
- `frontend/src/lib/suggestion-timing.ts`
- `frontend/src/services/api.ts`
- `frontend/tests/proactive-popup.test.cjs`
- `frontend/tests/product-suggestions.test.cjs`
- `frontend/tests/suggestion-transport.test.cjs` (new)
- `backend/app/routes/suggestions.py`
- `backend/app/services/suggestion_service.py` (new)
- `backend/app/services/ollama_service.py`
- `backend/app/schemas/suggestions.py`
- `backend/app/config.py` and `backend/.env.example` (documented configurable 45-second suggestion read timeout; frontend generation bound 53 seconds, capability request bound 8 seconds)
- `backend/test_suggestions.py`
- `backend/test_suggestion_lifecycle.py` (new)
- `backend/scripts/measure_popup_latency.py` (new)
- This report, `popup-model-live-results.json`, five `popup-latency-*.json` evidence files and popup validation logs.

The actual `.env` URLs were retained: Laya `http://127.0.0.1:5056/decide`, Ollama `http://localhost:11434/api/chat`, model `llama3.2:latest`; storefront API base remains `http://localhost:8000`. Other existing working-tree changes were preserved. No service was manually stopped/restarted or browser state fabricated.
