# Quantity-language fix

## Exact-message trace and root cause

`Reduce the iPhone 13 quantity to one` already selected `cart_action` in the rule provider because it contains “quantity.” ChatService's mutation regex accepted only increase/decrease with “quantity” immediately after the verb. It did not accept reduce/set/change or a product name before quantity. Therefore no mutation operation was created and the cart route returned generic instructions; the frontend received no command marker and left the cart unchanged.

The existing amount parser and frontend already supported absolute quantities via `to one` and `set_quantity`. That path was unreachable for the reported wording. Product matching also previously extracted names only after “quantity of/for,” not before “quantity.”

## Fix and ownership

The new shared `parse_cart_operation` recognizes increase/raise, decrease/reduce/lower, and set/change/update commands, including product-first and quantity-first forms. It extracts the explicit product reference and normalizes articles, case, punctuation and possessives. Cart IDs are looked up directly, and abbreviated names are matched against the catalog records for IDs already in the cart. Explicit absent names do not fall back to an unrelated selected/search product; multiple matching variants require clarification.

`to one` produces an absolute target of 1. `by one` remains a relative change. Set/change commands require an explicit absolute target. Stock checks, expected-quantity validation, and the existing zero-removes/negative-invalid minimum rules remain in place.

The backend returns a `SHOPAI_CART_ACTION` with product ID, expected quantity and target. It does not mutate browser state. The existing frontend handler applies the command through CartContext, recalculates count/subtotal and retains the existing localStorage persistence mechanism. No frontend runtime change was needed.

## Changed files

- `backend/app/services/cart_operations.py` (new shared parser)
- `backend/app/services/decision_provider.py`
- `backend/app/services/chat_service.py`
- `backend/test_cart_quantity_language.py` (new focused regressions)
- `frontend/tests/chat-cart.test.cjs` (exact command, totals and storage regression)
- `frontend/tests/verify-live-chat-bugs.cjs` (exact live command and absolute-target checks)
- This report, `quantity-language-live-results.json`, and new diagnostic logs.

## Actual results

- 7 focused quantity-language tests passed.
- 143 relevant backend tests passed, including cart totals, references, comparison, concurrency, budgets, stock and accessory regressions.
- 25 frontend tests passed, including command application, stock/stale-state checks, quantity/count/subtotal and persistence.
- 52 live HTTP chat requests passed against PostgreSQL (508 products), with actual frontend cart-command and totals helpers in a Node client harness.
- The exact command returned `{"action":"set_quantity","product_id":"apple-iphone-13-blue-128gb","expected_quantity":2,"quantity":1}`. The live reconstructed fixture began with 4 units totaling ₹1,07,298 and ended with 3 units totaling ₹57,398. The extra two products were real catalog rows (₹1,199 screen protector and ₹6,299 memory card); these were not claimed to be the unknown other items in the user's browser cart. Totals were calculated from API values, not hardcoded responses.
- Each requested phrase also changed a quantity of 4 directly to 1, proving absolute rather than one-unit-decrement behavior.
- Every live request recorded `rule-based`, zero Laya calls and zero Ollama calls. Cart operations did not start product search. Frontend HTTP status was 200.
- Whitespace checks passed for changed tracked files.

Commands:

```powershell
# backend
& ../.venv/Scripts/python.exe -m unittest test_cart_quantity_language
& ../.venv/Scripts/python.exe -m unittest test_cart_quantity_language test_cart_totals test_chat_screenshot_regressions test_rule_decision_provider test_chat_followups test_chat_regressions test_laya_contract test_search_budget_regressions test_chat_concurrency test_accessory_compatibility test_short_accessory
# frontend
& 'C:/Program Files/nodejs/node.exe' --test tests/chat-cart.test.cjs tests/suggestion-click.test.cjs tests/product-suggestions.test.cjs
& 'C:/Program Files/nodejs/node.exe' --max-old-space-size=256 tests/verify-live-chat-bugs.cjs quantity-language-live-results.json
```

The running single-worker backend was restarted with rules active, Ollama disabled, and both Hugging Face offline flags set. New startup logs are `lowram-backend-20261010-124621-919.*.log`. Laya/ModernBERT was not loaded and the approved checkpoint was not changed.

## Manual-browser verification blocker

The computer-use inventory returned no apps or browser surfaces. Attempting to open the website through Chrome returned `Browser is not available: chrome`. The requested manual browser verification could therefore not be performed. The user's browser cart was not read or changed by the automation. The live API/frontend-logic check and isolated persistence tests do not constitute rendered-browser validation. To verify in the existing browser, resend `Reduce the iPhone 13 quantity to one`; assuming the reported cart is still 4 units totaling ₹1,07,298 with this iPhone at quantity 2, the expected result is quantity 1, 3 units and ₹57,398.
