# Inspected files — 9 October 2026

Reads include selected sections and artifact parsing. Dependency/model binary/backup trees and every historical log were not fully audited. Private settings were inspected through an allowlist. Git branch/status/history and read-only live service/database checks supplement these reads.

| Exact path | Contribution |
|---|---|
| .gitignore | Architecture, configuration or backend behavior |
| README.md | Architecture, configuration or backend behavior |
| backend/.env | Allowlisted endpoint/schema/key presence; credentials withheld |
| backend/.env.example | Allowlisted endpoint/schema/key presence; credentials withheld |
| backend/app/config.py | Architecture, configuration or backend behavior |
| backend/app/database/ingest.py | Architecture, configuration or backend behavior |
| backend/app/database/session.py | Architecture, configuration or backend behavior |
| backend/app/main.py | Architecture, configuration or backend behavior |
| backend/app/models/product.py | Architecture, configuration or backend behavior |
| backend/app/routes/chat.py | Architecture, configuration or backend behavior |
| backend/app/routes/health.py | Architecture, configuration or backend behavior |
| backend/app/routes/products.py | Architecture, configuration or backend behavior |
| backend/app/routes/suggestions.py | Architecture, configuration or backend behavior |
| backend/app/schemas/chat.py | Architecture, configuration or backend behavior |
| backend/app/schemas/suggestions.py | Architecture, configuration or backend behavior |
| backend/app/services/chat_service.py | Architecture, configuration or backend behavior |
| backend/app/services/laya_client.py | Typed decision contract/runtime/model provenance |
| backend/app/services/llm_service.py | Architecture, configuration or backend behavior |
| backend/app/services/ollama_service.py | Architecture, configuration or backend behavior |
| backend/app/tools/product_search_tool.py | Architecture, configuration or backend behavior |
| backend/requirements.txt | Architecture, configuration or backend behavior |
| backend/suggestion-click-results.json | Saved measurements, scored records or model provenance |
| backend/suggestion-performance-results.json | Saved measurements, scored records or model provenance |
| backend/test_backend.py | Existing regression assertions and fixture behavior |
| backend/test_chat_regressions.py | Existing regression assertions and fixture behavior |
| backend/test_suggestion_click.py | Existing regression assertions and fixture behavior |
| backend/test_suggestions.py | Existing regression assertions and fixture behavior |
| benchmark_results/laya_vs_bypass_2026-09-30.csv | Saved measurements, scored records or model provenance |
| documentation/shopai_technical_audit_2026-10-07.md | Historical comparison only; not current live proof |
| evaluation/jev_benchmark/config.py | Benchmark runner, scoring or dataset parsing |
| evaluation/jev_benchmark/dataset/typed_decisions_test.json | Benchmark runner, scoring or dataset parsing |
| evaluation/jev_benchmark/metrics.py | Benchmark runner, scoring or dataset parsing |
| evaluation/jev_benchmark/results/baseline_v2_20261004_raw.jsonl | Saved measurements, scored records or model provenance |
| evaluation/jev_benchmark/results/baseline_v2_20261004_summary.json | Saved measurements, scored records or model provenance |
| evaluation/jev_benchmark/results/baseline_v2_20261006_214159_summary.json | Saved measurements, scored records or model provenance |
| evaluation/jev_benchmark/results/laya_jev_benchmark_summary.json | Saved measurements, scored records or model provenance |
| evaluation/jev_benchmark/run_baseline_v2.py | Benchmark runner, scoring or dataset parsing |
| evaluation/jev_benchmark/runner.py | Benchmark runner, scoring or dataset parsing |
| evaluation/laya_specialist_onnx_isolated/benchmark/runs/20261005_184532_IST/specialist_raw.jsonl | Benchmark runner, scoring or dataset parsing |
| evaluation/laya_specialist_onnx_isolated/benchmark/runs/20261005_184532_IST/specialist_summary.json | Benchmark runner, scoring or dataset parsing |
| frontend/AGENTS.md | Architecture, configuration or backend behavior |
| frontend/package.json | Architecture, configuration or backend behavior |
| frontend/src/components/storefront/CartDrawer.tsx | Frontend API, context, navigation or rendering |
| frontend/src/components/storefront/CategoryNav.tsx | Frontend API, context, navigation or rendering |
| frontend/src/components/storefront/Chatbot.tsx | Frontend API, context, navigation or rendering |
| frontend/src/components/storefront/ChatbotPanel.tsx | Frontend API, context, navigation or rendering |
| frontend/src/components/storefront/Navbar.tsx | Frontend API, context, navigation or rendering |
| frontend/src/components/storefront/ProductCard.tsx | Frontend API, context, navigation or rendering |
| frontend/src/components/storefront/ProductDetails.tsx | Frontend API, context, navigation or rendering |
| frontend/src/components/storefront/ProductSuggestionPopup.tsx | Frontend API, context, navigation or rendering |
| frontend/src/components/storefront/SearchBar.tsx | Frontend API, context, navigation or rendering |
| frontend/src/components/storefront/SiteFooter.tsx | Frontend API, context, navigation or rendering |
| frontend/src/context/CartContext.tsx | Frontend API, context, navigation or rendering |
| frontend/src/lib/chat-cart.ts | Frontend API, context, navigation or rendering |
| frontend/src/lib/product-suggestions.ts | Frontend API, context, navigation or rendering |
| frontend/src/router.tsx | Frontend API, context, navigation or rendering |
| frontend/src/routes/__root.tsx | Frontend API, context, navigation or rendering |
| frontend/src/routes/products.$productId.tsx | Frontend API, context, navigation or rendering |
| frontend/src/routes/products.index.tsx | Frontend API, context, navigation or rendering |
| frontend/src/services/api.ts | Frontend API, context, navigation or rendering |
| frontend/tests/chat-cart.test.cjs | Existing regression assertions and fixture behavior |
| frontend/tests/product-suggestions.test.cjs | Existing regression assertions and fixture behavior |
| frontend/tests/suggestion-click.test.cjs | Existing regression assertions and fixture behavior |
| frontend/vite.config.ts | Architecture, configuration or backend behavior |
| laya_service/package.json | Typed decision contract/runtime/model provenance |
| laya_service/server.js | Typed decision contract/runtime/model provenance |
| laya_service/switchable_server.mjs | Typed decision contract/runtime/model provenance |
| laya_v2_service/.venv/Lib/site-packages/laya/agent.py | Typed decision contract/runtime/model provenance |
| laya_v2_service/README.md | Typed decision contract/runtime/model provenance |
| laya_v2_service/laya_Model/infer.py | Typed decision contract/runtime/model provenance |
| laya_v2_service/requirements.txt | Typed decision contract/runtime/model provenance |
| laya_v2_service/results/jev_compatibility_note.md | Saved measurements, scored records or model provenance |
| laya_v2_service/results/jev_full_20261008T115135_157161Z/laya_jev_benchmark_results.json | Saved measurements, scored records or model provenance |
| laya_v2_service/results/jev_full_20261008T115135_157161Z/laya_jev_benchmark_summary.json | Saved measurements, scored records or model provenance |
| laya_v2_service/results/model_verification.json | Saved measurements, scored records or model provenance |
| laya_v2_service/run_benchmark.py | Typed decision contract/runtime/model provenance |
| laya_v2_service/service.py | Typed decision contract/runtime/model provenance |
| laya_v2_service/shopai_questions.json | Typed decision contract/runtime/model provenance |
| run_v2_jev.py | Architecture, configuration or backend behavior |
| scripts/expand_poorvika_catalog.py | Selected acquisition sections, not executed |
| scripts/scrape_poorvika_products.py | Selected acquisition sections, not executed |