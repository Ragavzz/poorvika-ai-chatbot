# Deterministic cart-total queries

## Root cause

The rule provider relied on the words cart/checkout/quantity to classify cart requests. “What is my current total?” therefore became a general query; wording containing “price” could instead become product details. ChatService's cart guards also lacked the implicit-total phrases. Finally, its concise-total formatter excluded messages containing “items,” which rejected “the total price of all items.” The frontend already sends current cart IDs, prices and quantities on every request through `shopai_client_context`, using its latest-cart ref; the integration itself did not need a runtime change.

## Fix

A shared recognizer covers the requested five phrases and related cart-total/subtotal wording. The provider returns `cart_action`; routing keeps the message out of product discovery, product details and generation; the existing deterministic cart formatter computes the total from the supplied current cart snapshot. Indian number grouping matches the storefront currency convention. The existing calculation is item price × quantity, summed across the cart. The current drawer uses this same subtotal as the total with free shipping; no new fees, taxes or discounts are added. Quantities count units, as in the existing CartContext `totalItems` calculation.

Empty snapshots return a zero total. Missing snapshots return a concise request to open the cart and retry, rather than claiming the backend can inspect browser localStorage. Each incoming snapshot replaces any previous request's cart for summary purposes. Session isolation, IDs, frontend persistence and stock/mutation logic are retained.

## Files changed

- `backend/app/services/cart_queries.py` — new shared recognizer and INR formatting.
- `backend/app/services/decision_provider.py` — explicit cart-total selection.
- `backend/app/services/chat_service.py` — deterministic summary routing, latest-snapshot handling and missing-snapshot response.
- `backend/test_cart_totals.py` — eight focused tests covering all phrases, empty/current totals, add/increase/decrease/remove, session isolation, no invented charges and no search/generation.
- `frontend/tests/suggestion-click.test.cjs` — verifies actual ChatbotPanel sends the latest cart snapshot after changes.
- `frontend/tests/verify-live-chat-bugs.cjs` — extends the live HTTP/client-handler checker with all five phrases across five cart states and a separate output filename.
- This report, `cart-total-live-results.json`, and new diagnostic logs.

No frontend runtime change, configuration change, dependency installation or model/checkpoint change was required. Existing working-tree changes were preserved.

## Actual results

- Focused cart-total tests: **8 passed**.
- Relevant backend regressions: **136 passed**, including references, comparisons, stock/cart safety, context, concurrency, budgets and accessories.
- Relevant frontend checks: **24 passed**, including cart commands, totals/persistence and latest-snapshot submission.
- Live check: **46 HTTP chat requests passed**, including **25 cart-total summaries** (five phrases × empty/add/increase/decrease/remove states). The checker uses real catalog records from PostgreSQL (508 products), actual frontend cart-command/quantity/totals helpers in a Node client harness, and actual backend timing logs. Cart-summary values are computed dynamically from those records. No user's browser cart was read or modified by this checker.
- Every live request recorded `rule-based`, zero Laya calls and zero Ollama calls. Cart-summary requests recorded no product-search start. Frontend returned HTTP 200; backend health confirmed PostgreSQL and disabled Ollama generation.
- Whitespace checks passed for changed tracked files.

Commands:

```powershell
# From backend
& ../.venv/Scripts/python.exe -m unittest test_cart_totals
& ../.venv/Scripts/python.exe -m unittest test_cart_totals test_chat_screenshot_regressions test_rule_decision_provider test_chat_followups test_chat_regressions test_laya_contract test_search_budget_regressions test_chat_concurrency test_accessory_compatibility test_short_accessory
# From frontend
& 'C:/Program Files/nodejs/node.exe' --test tests/chat-cart.test.cjs tests/suggestion-click.test.cjs tests/product-suggestions.test.cjs
& 'C:/Program Files/nodejs/node.exe' --max-old-space-size=256 tests/verify-live-chat-bugs.cjs cart-total-live-results.json
```

The single backend worker was restarted with `DECISION_PROVIDER=rules`, `OLLAMA_ENABLED=false`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`. New startup logs use `lowram-backend-20261010-123913-614.*.log`. The frontend remains on port 8080. No Laya/ModernBERT model was loaded, and no live Laya validation was performed. Browser rendering remains unverified because there is no connected browser surface.
