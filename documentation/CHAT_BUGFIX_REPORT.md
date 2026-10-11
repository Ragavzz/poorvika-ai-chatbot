# Chat reference, comparison, cart and category fixes

## Root causes and changes

1. Reference parsing treated words such as “cheaper” and “one” as search terms. The resolver now handles cheaper/cheapest against saved results; ties list only the lowest-price candidates. Ambiguous pronouns list the current products and their prices. The word “one” remains valid inside names such as Acer One.
2. There was no comparison route. Compare and best-specification requests now retrieve saved result IDs directly, show price, brand, stock and the actual specifications, and mark unavailable fields as not listed. Best specifications asks which attribute matters rather than inventing an overall ranking. The most recent nonempty search set is retained separately so viewing one product does not collapse a later comparison.
3. Quantity mutations previously searched catalog text and resolved against search results, not the client cart. Mutations now resolve only IDs already present in the supplied cart, with catalog names/specifications used to match abbreviations. Single-item carts and selected/ordinal item references are supported; multiple ambiguous items require a focused choice. Absolute “to two” and relative “by two” quantities use an explicit `set_quantity` command with product ID and expected current quantity.
4. Cart-view patterns missed “show me my cart”; discovery recovery could then turn cart phrases into searches. Cart/quantity requests now bypass search recovery. Unsupported actions return capabilities without emitting a mutation. Existing tests for negated/question-form add requests now assert the safer cart route rather than the previous product-search route.
5. Category extraction used one if/elif value. Multiple requested categories now use the existing ProductSearchTool per category, preserve all filters, interleave and deduplicate results, and report categories with no matching results under the current constraints.
6. Zero-result messages leaked internal filter diagnostics, and frontend formatting rejected any response mentioning technical words even inside legitimate specifications. Zero-result messaging now stays within actual catalog-search branches and keeps brand/budget constraints in plain language. Presentation filtering targets diagnostic patterns rather than valid product vocabulary.

## Cart ownership, inventory, totals and persistence

React CartContext/localStorage remains the cart owner; there is no new backend cart API. Chat sends a current client snapshot. The backend returns an instruction; the frontend checks the expected quantity, fetches current inventory for increases and applies the existing cart mechanism. Fresh inventory is passed to CartContext. Catalog APIs expose the existing stock field. Shared quantity rules also limit drawer changes and additions. Subtotal and displayed total continue using the same quantity × catalog price calculation and existing free-shipping behavior. Cart storage continues using `shopai_cart_items`.

## Files changed in this task

- `backend/app/services/chat_service.py`
- `backend/app/services/decision_provider.py`
- `backend/app/tools/product_search_tool.py`
- `backend/app/models/product.py`
- `backend/test_chat_screenshot_regressions.py` (new)
- `backend/test_chat_regressions.py` (two route expectations updated; mutation-safety assertions retained)
- `frontend/src/lib/chat-cart.ts`
- `frontend/src/lib/cart-state.ts` (new shared quantity, totals and persistence helpers)
- `frontend/src/lib/shopping-response.ts`
- `frontend/src/context/CartContext.tsx`
- `frontend/src/services/api.ts`
- `frontend/tests/chat-cart.test.cjs`
- `frontend/tests/verify-live-chat-bugs.cjs` (new explicit live checker)
- This report, `chat-bugfix-live-results.json`, and new diagnostic logs.

Existing unrelated working-tree changes were preserved. No model weights, checkpoints, dependencies or Windows settings were changed.

## Actual verification

- 128 focused backend tests passed, including screenshot scenarios, existing context/follow-ups, concurrency, Laya contract boundaries, budgets, accessory compatibility and abbreviated accessory names.
- 23 frontend tests passed, including explicit quantity commands, fresh-stock limits, stale-cart races, subtotal recalculation, localStorage serialization/reload, removal, existing cart commands and suggestion-click behavior.
- Targeted frontend ESLint: zero errors, two existing `react-refresh/only-export-components` warnings in CartContext.
- 20 live chat requests passed against PostgreSQL (508 products). The live checker executes the real frontend command handler and quantity/totals reducer in a Node client harness and retrieves real products via HTTP. It reads provider and operation counts from the actual backend log. Every request used `rule-based`, with zero Laya and Ollama calls. Cart/comparison requests had no product-search start. Frontend returned HTTP 200.
- `chat-bugfix-live-results.json` records each message, full response, IDs and actual backend timing/provider fields.

Commands, from the relevant directories:

```powershell
# backend
& ../.venv/Scripts/python.exe -m unittest test_chat_screenshot_regressions test_rule_decision_provider test_chat_followups test_chat_regressions test_laya_contract test_search_budget_regressions test_chat_concurrency test_accessory_compatibility test_short_accessory
# frontend
& 'C:/Program Files/nodejs/node.exe' --test tests/chat-cart.test.cjs tests/suggestion-click.test.cjs tests/product-suggestions.test.cjs
& 'C:/Program Files/nodejs/node.exe' --max-old-space-size=256 tests/verify-live-chat-bugs.cjs
& 'C:/Program Files/nodejs/node.exe' --max-old-space-size=256 node_modules/eslint/bin/eslint.js src/lib/chat-cart.ts src/lib/cart-state.ts src/lib/shopping-response.ts src/context/CartContext.tsx src/services/api.ts
```

The running backend remains a single worker with `DECISION_PROVIDER=rules`, `OLLAMA_ENABLED=false`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`. The frontend remains on port 8080. The production defaults and approved Laya checkpoint are unchanged. No live Laya validation was attempted.

## Limits

No new screenshot attachment or connected browser surface was available in this task. Verification covers the described screenshot sequences, live HTTP/catalog behavior and actual frontend cart logic in a Node harness. The rendered cart drawer and browser localStorage were not directly inspected; persistence was verified by the exact shared storage helpers with an isolated storage interface. Inventory checks remain point-in-time checks rather than purchase reservations. No memory-intensive full build or full test suite was run.
