# Proactive popup fix

The popup previously waited for getProductSuggestions -> /api/chat/suggestions -> Ollama. It returned null while pending or on error, so disabled/unavailable generation suppressed the popup. It had no independent readiness delay.

The popup now observes the existing product query using skipToken, waits 1200 ms after valid matching product data becomes available, and builds four prompts synchronously from product name/category. Existing filtered listing triggers remain supported. Initial suggestions make no API/LLM request. Route transitions cancel timers and reject mismatched product data. Dismissal is retained per context during this mounted browsing session; a full refresh starts a new session. Opening the manual assistant also consumes that context's prompt. The popup is portaled to document.body with fixed positioning, z-50, viewport-bounded width/height, and scrolling.

Changed runtime files:
- frontend/src/components/storefront/ProductSuggestionPopup.tsx
- frontend/src/lib/product-suggestions.ts

Changed tests:
- frontend/tests/proactive-popup.test.cjs (new)
- frontend/tests/suggestion-click.test.cjs (manual toggle regression added)

Validation:
- 34 focused frontend tests passed, zero failures. Includes readiness after refresh, route cancellation/new context, dismissal/revisit, manual assistant, one timer, selection product ID, listing triggers, portal/layout class constraints, and real React Query observation without duplicate fetching.
- Changed runtime files: ESLint passed.
- Production build passed (client, SSR and Nitro). Existing tsconfig-paths and large-chunk warnings remain.
- Actual Node timer measurement: 1256.4 ms. This measures the test-rendered component after a real timer; it is not browser paint timing.
- Live HTTP GETs on Samsung Watch5 Pro and another product URL returned HTML with status 200. Updated popup module served successfully.
- Backend healthy: PostgreSQL connected, 508 products, rules provider, Ollama disabled. No Laya model loaded.
- Browser automation inventory contained no browsers. Direct refresh/navigation visual behavior, desktop/mobile rendering and actual browser paint latency were NOT manually verified. Component tests and HTTP checks do not establish visual browser success.

Commands (frontend working directory):
```powershell
node --test tests/proactive-popup.test.cjs tests/suggestion-click.test.cjs tests/product-suggestions.test.cjs tests/chat-cart.test.cjs
node --max-old-space-size=256 node_modules/eslint/bin/eslint.js src/components/storefront/ProductSuggestionPopup.tsx src/lib/product-suggestions.ts
$env:NODE_OPTIONS='--max-old-space-size=512'
$env:RAYON_NUM_THREADS='2'
node node_modules/vite/bin/vite.js build
$env:NODE_OPTIONS='--max-old-space-size=384'
node node_modules/vite/bin/vite.js dev --host 127.0.0.1 --port 8080 --strictPort
```
The known existing Vite process was paused for the build, then restarted hidden with new stdout/stderr logs. Backend was not restarted. Frontend PID after restart: 18368. Logs: proactive-popup-regressions-final.log, proactive-popup-lint.log, proactive-popup-build.log, proactive-frontend-20261010-125723-639.*.log. Structured results: documentation/proactive-popup-results.json.
