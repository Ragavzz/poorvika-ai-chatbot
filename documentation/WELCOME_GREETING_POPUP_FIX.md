# Welcome, greeting and proactive popup verification — 2026-10-10

## Root causes and targeted changes

- `frontend/src/components/storefront/ChatbotPanel.tsx`: the initial message array was empty. It now starts with the requested static UI welcome. The existing `Chatbot` retains the mounted panel after its first opening, preserving the welcome and subsequent history across closing/reopening without adding new messages.
- `backend/app/services/decision_provider.py`: added a complete-message greeting matcher, including good morning/afternoon/evening. It does not match product requests prefixed with a greeting, short product names, follow-ups or cart commands.
- `backend/app/services/chat_service.py`: after the configured decision call, complete greetings take a dedicated general-query generation path before product context lookup or catalog recovery. This preserves the Laya decision layer and calls real Ollama when enabled. Disabled/unavailable generation retains the existing truthful 503. General chat is explicitly marked for its own prompt.
- `backend/app/services/ollama_service.py`: the old default prompt mandated a catalog error for empty context, including greetings. General chat now has a separate prompt. Suggestion generation explicitly forbids invented product names and numeric facts; unsupported numeric facts reject the entire result. Equivalent catalog price formatting is allowed. No canned assistant response or suggestion fallback was added.
- `frontend/src/components/storefront/ProductSuggestionPopup.tsx`: reports capability failures, disabled generation and model errors to the console. The existing working-tree popup implementation was retained: it is mounted by `Chatbot`, observes the product page's exact query cache key, follows search/category route context, waits 1.2 seconds, requires validated model output, portals to the body, and remembers dismissal per context for the mounted storefront session. Product changes use separate query keys; old session-storage suggestions are not read. Recommendations are follow-up question strings, so no fabricated product cards or identifiers are introduced.

The repository already contained substantial uncommitted fixes and validation artifacts. They were preserved. Environment configuration, model weights and service processes were not changed.

## Tests and evidence

- Backend: **205 tests passed** across greeting, suggestion, follow-up, search, Laya contract, provenance, concurrency, comparison and cart regression modules. See `welcome-backend-validation.log`. Some existing test fixtures emit SQLite resource warnings.
- Frontend: **37 tests passed**, including initial welcome/reopen, history/error separation, suggestion clicks, product navigation, dismissal, disabled/failed generation, popup timing/layout and cart reducers. See `welcome-frontend-validation.log`. These use Node component harnesses and React Query observers, not a rendered browser.
- Targeted lint on the two changed UI components: passed, no output/errors (`welcome-targeted-lint.log`).
- Repository-wide `npm run lint`: failed with **2,068 errors and 18 warnings**, largely formatting/line-ending problems across existing files and test scripts (`welcome-lint-validation.log`). No broad formatting rewrite was attempted.
- Production `npm run build`: passed (`welcome-build-validation.log`).
- Independent live inference: approved Laya V2 returned a valid model decision for the Sony budget request; Ollama `llama3.2:latest` generated a friendly greeting and validated shopping questions. See `welcome-model-live-results.json` for URLs, actual outputs and running backend health (PostgreSQL, 508 products, Laya selected, Ollama enabled).
- Current-source live orchestration and a real iPhone product suggestion request are recorded in `welcome-pipeline-live-results.json`. The greeting uses one Laya call and one Ollama call; Sony earphones under ₹1000 use real PostgreSQL search and return Sony MDR-EX15AP at ₹829, without generative catalog calculations.

**No rendered browser verification was executed.** Popup visibility, responsive stacking and checkout-demo behavior still require a browser acceptance check; lifecycle/layout and cart/comparison regressions are covered by the automated harnesses. Model questions remain probabilistic: unsupported numeric output is hidden instead of substituted, and semantic relevance is primarily enforced by the supplied context and generation instructions.

## Other changed files

- `backend/test_welcome_greetings.py` (new)
- `backend/test_suggestions.py`
- `frontend/tests/suggestion-click.test.cjs`
- `backend/scripts/verify_welcome_models.py` (new)
- `backend/scripts/verify_welcome_pipeline.py` (new)
- This report, the two welcome live-result JSON files and four validation logs.
