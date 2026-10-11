# Consolidated investigation and validation — 2026-10-10

## Scope and preserved work

Inspected git status, the four recent commits, frontend/AGENTS.md, existing diffs and tests, and the proactive popup, cart totals and quantity-language reports and JSON evidence. Existing working changes were retained. No reset, revert, dependency installation, checkpoint change or diagnostic-log replacement occurred. New validation logs and reports have a consolidated prefix. The backend was not restarted; the known Vite server alone was paused for the capped production build and restarted on port 8080.

## Confirmed causes

The previous functional causes remain addressed:

- Popup: initial rendering waited for the suggestions endpoint/Ollama and disappeared on error. The current component uses local product context and a 1200 ms timer, with cancellation, dismissal tracking and a body portal.
- Cart totals: implicit cart-total phrases previously became general/details intents. The shared recognizer now selects deterministic cart summary using the latest client snapshot.
- Quantity: product-first reduce/set/change wording did not produce a cart command. The shared parser now resolves current-cart IDs/names and interprets “to one” as absolute quantity 1.

Two additional failures were reproduced in this investigation:

1. The concurrency regression expected a slow Ollama call regardless of configuration. With OLLAMA_ENABLED=false, correct runtime behavior skips generation and completes immediately, so the assertion failed. The test now isolates thread-pool scheduling with a stubbed response wrapper. A new regression separately proves that disabled generation calls no Ollama client. This is isolated test coverage, not live model validation.
2. Relevant-file ESLint reported 186 formatting errors in ChatbotPanel.tsx (CRLF/indentation/wrapping). Prettier fixed them without changing chat behavior.

No remaining functional failure was reproduced by the current component tests or live API/client-helper scenarios. Browser behavior remains unverified.

## Files changed in this consolidated pass

- backend/test_chat_concurrency.py: remove the enabled-generation assumption and add disabled-generation coverage.
- frontend/src/components/storefront/ChatbotPanel.tsx: formatting only; preserved session, cart, suggestion and history behavior.
- This report, consolidated-live-results-20261010.json, consolidated-runtime-20261010.json, and new consolidated logs: evidence and manual validation instructions.
- lowram-frontend.pid: updated to the restarted Vite process; generated production build artifacts refreshed by the build.

Earlier modified/untracked application files remain present and were not reverted.

## Actual checks

| Check | Result |
|---|---|
| Focused cart total + quantity | 15 passed |
| Concurrency after correction | 3 passed |
| Relevant backend regression modules | 144 passed, zero failures |
| Frontend popup/cart/suggestion suites | 34 passed, zero failures |
| Live HTTP + actual frontend command/totals helpers | 52 chat requests passed, real PostgreSQL catalog |
| Exact iPhone quantity command | quantity 2 → 1; reconstructed fixture 4 units / ₹1,07,298 → 3 units / ₹57,398 |
| Provider for every live chat request | rule-based, zero Laya calls, zero Ollama calls |
| Cart/comparison live search guard | no ProductSearchTool start for those actions |
| Popup real Node timer | 1252.2 ms; not browser paint timing |
| Relevant frontend lint (eight runtime files) | zero errors; two existing CartContext Fast Refresh warnings |
| Production build | passed client, SSR and Nitro; existing large-chunk and tsconfig-paths warnings |
| Whitespace check on this pass's changed tracked files | passed |
| Browser automation | no apps/browsers exposed; no visual scenario verified |

The reconstructed live cart uses real API products and calculated prices; it does not read or modify the user's browser cart. Isolated tests use SQL fixtures and stubs deliberately; live HTTP evidence is separate. HTTP HTML responses do not prove hydrated frontend rendering. No full memory-intensive backend discovery suite was run, and the lint result is scoped rather than a claim that the whole repository is lint-clean.

Evidence: consolidated-focused-20261010.log, consolidated-backend-regressions-20261010.log (initial failure), consolidated-backend-final-20261010.log (new test assertion corrected), consolidated-concurrency-final-20261010.log, consolidated-backend-verified-20261010.log, consolidated-frontend-final-20261010.log, consolidated-lint-initial-20261010.log, consolidated-lint-final-20261010.log, consolidated-production-build-20261010.log and consolidated-live-20261010.log. All intermediate failures were retained.

## Exact commands

Backend directory:

```powershell
$env:DECISION_PROVIDER='rules'
$env:OLLAMA_ENABLED='false'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
& ../.venv/Scripts/python.exe -m unittest test_cart_totals test_cart_quantity_language
& ../.venv/Scripts/python.exe -m unittest test_cart_quantity_language test_cart_totals test_chat_screenshot_regressions test_rule_decision_provider test_chat_followups test_chat_regressions test_laya_contract test_search_budget_regressions test_chat_concurrency test_accessory_compatibility test_short_accessory
```

Frontend directory:

```powershell
node --max-old-space-size=256 --test tests/proactive-popup.test.cjs tests/suggestion-click.test.cjs tests/product-suggestions.test.cjs tests/chat-cart.test.cjs
node --max-old-space-size=256 node_modules/eslint/bin/eslint.js src/components/storefront/ChatbotPanel.tsx src/components/storefront/ProductSuggestionPopup.tsx src/context/CartContext.tsx src/lib/chat-cart.ts src/lib/cart-state.ts src/lib/product-suggestions.ts src/lib/shopping-response.ts src/services/api.ts
node --max-old-space-size=256 tests/verify-live-chat-bugs.cjs consolidated-live-results-20261010.json
$env:NODE_OPTIONS='--max-old-space-size=512'
$env:RAYON_NUM_THREADS='2'
node node_modules/vite/bin/vite.js build
$env:NODE_OPTIONS='--max-old-space-size=384'
node node_modules/vite/bin/vite.js dev --host 127.0.0.1 --port 8080 --strictPort
```

The actual Vite restart used Start-Process with WindowStyle Hidden and new stdout/stderr logs. The running backend remains in rules mode with Ollama disabled. Neither local inference service was started.

## Manual browser checks still required

These are instructions, not passed results. Use a fresh private browser session for cart fixtures so the existing user's cart is preserved.

1. **Direct refresh and timing:** Open http://127.0.0.1:8080/products/samsung-galaxy-watch5-pro-lte-45-mm-gray-titanium-sm-r925fztainu directly. Refresh. Once the product name/details appear, measure until the four suggestions appear; expect approximately 1–2 seconds. To capture existing timing diagnostics, run `sessionStorage.setItem('shopai:suggestion-diagnostics','1')` in the console before refreshing; inspect `[SUGGESTION TIMING]` and `context_to_visible_ms`. Check the Network panel: initial popup must not request `/api/chat/suggestions` or `/api/chat`.
2. **Route changes and dismissal:** Dismiss the popup with its X, wait at least five seconds and confirm it remains closed. Navigate within the app to another product without refreshing. Confirm new product suggestions after 1–2 seconds and no old watch name. Return to the dismissed watch within the same browsing session: it should remain dismissed. A full refresh intentionally starts a fresh popup session.
3. **Manual chat/history:** Click Shopping Assistant before the popup timer completes; chat should open and the pending popup should not appear. Send “hello,” close and reopen chat; history should remain. Navigate to a new product with chat closed, click “Tell me more…” on its popup and verify one submitted message and that product's details.
4. **Listing/context:** Use the site's search for “laptops” or a category listing. Verify context-specific suggestions without a generation request. Search “Show laptops under 100000,” then “Only HP laptops,” then “Compare the first two products.” Confirm comparison reflects the current HP results and keeps the budget. Ask “Which one has the best specifications?” and confirm actual specs/comparison or focused clarification rather than invented ranking.
5. **Cart totals and exact quantity:** In the fresh private session, ask “What is my current total?” with an empty cart; expect ₹0 and 0 items. Open http://127.0.0.1:8080/products/apple-iphone-13-blue-128gb and add it. Send “set iPhone 13 quantity to 2”; drawer must show quantity 2 and ₹99,800 if the catalog price remains ₹49,900. Ask both “What is my current total?” and “What is the total price of all items?”; compare to the drawer. Send “Reduce the iPhone 13 quantity to one”; expect quantity 1, one unit and ₹49,900. Ask “What is my updated total?”; it must match. Refresh the page and reopen the cart to verify persistence. Send “Increase the iPhone 13 quantity to two,” then “decrease quantity to 1,” then “change the quantity to one”; each must match the drawer's latest quantity and totals. Send “Show me my cart,” then “Remove that product from my cart”; summary must become empty/₹0.
6. **Missing/ambiguous/stock:** With the iPhone absent, send “Reduce the iPhone 13 quantity to one”; expect a missing-item explanation and no mutation. If the live catalog has two iPhone 13 variants, add both and repeat that command; expect clarification, then use the exact product ID `apple-iphone-13-blue-128gb` to target only blue. Request a quantity above the API's current stock; expect rejection. Quantity zero should remove the item; negative/fractional quantities should be rejected.
7. **Layout:** Repeat popup refresh, dismissal, selection and manual-button checks at desktop 1366×768 and mobile 390×844. Confirm the popup is above content, text wraps, all suggestions and dismiss control remain reachable, and there is no horizontal clipping or duplicate popup. No desktop/mobile screenshot verification was available during this investigation.

