# Testing and benchmarks

[Main handover](FINAL_PROJECT_HANDOVER.md) · [Operations](DEPLOYMENT_AND_OPERATIONS.md)

Audit date: 10 October 2026. Fresh tests are separated from **saved historical inference runs**. No benchmark inference, training, model export, cloud-judge scoring or model download was performed for this handover.

## Fresh verification

| Check | Actual result | New evidence |
|---|---|---|
| Backend selected complete regression suite | 138 executions PASS, exit 0, 41.684 seconds | [backend.log](handover_evidence_2026-10-10/backend.log) |
| Frontend cart/suggestions/click helpers | 18 PASS, exit 0 | [frontend.log](handover_evidence_2026-10-10/frontend.log) |
| TypeScript --noEmit | exit 0 | [types.log](handover_evidence_2026-10-10/types.log) |
| Production build | exit 0 | [build.log](handover_evidence_2026-10-10/build.log) |
| Authored Markdown checks | PASS: links/anchors/fences/whitespace/bounded secret patterns | [documentation_checks.json](handover_evidence_2026-10-10/documentation_checks.json) |
| Repository-wide git diff --check | FAIL, exit 2: naturally appended CRLF lines in existing Laya runtime log are reported as trailing whitespace; log preserved | [diff_check.log](handover_evidence_2026-10-10/diff_check.log) |
| Existing service health | PostgreSQL 508; V2 loaded on 5056; frontend 8080 and Ollama reachable; 5055 refused | [health.json](handover_evidence_2026-10-10/health.json) |
| Real API smoke | Short protector ₹999 Out of Stock; cart addition refused; Sony ₹829 under ₹1000 | [smoke.json](handover_evidence_2026-10-10/smoke.json) |

Counts are executions, not 138 unique user journeys. Suggestion-click tests inherit existing test methods, repeating scenarios. Main eight tests use temporary SQLite with actual catalog ingestion; some call real Laya and legacy LLM behavior. Chat/action, accessory, suggestion-contract and concurrency regressions use model mocks. A passed SQLite fixture is not PostgreSQL production acceptance. Fresh API smoke uses actual Laya V2 and PostgreSQL, independently of these mocks.

Frontend tests transpile helpers and use a hook harness; they are not rendered browser/DOM/accessibility tests. Browser acceptance remains unverified/previously blocked (no available iab browser). No payment/delivery, catalog import into the active DB, clean-clone install, deployed host, load/P95 or exhaustive security check was executed.

Existing warnings remain: Starlette/httpx deprecation, unclosed SQLite test resources, large build chunks/plugin overhead/inlineDynamicImports and WASM fallback. Successful build does not mean these warnings were resolved.

## Reproducible commands

From backend:

```powershell
& ../.venv/Scripts/python.exe -m unittest test_backend test_chat_regressions test_suggestions test_suggestion_click test_laya_contract test_chat_concurrency test_search_budget_regressions test_accessory_compatibility test_short_accessory
```

Requires the canonical 508-row JSONL fixture and current V2 for real calls. An unavailable real service can fail integration assertions; report that rather than relaxing them.

From frontend:

```powershell
node --test tests/chat-cart.test.cjs tests/product-suggestions.test.cjs tests/suggestion-click.test.cjs
node node_modules/typescript/bin/tsc --noEmit
node node_modules/vite/bin/vite.js build
```

From root: git diff --check. Package scripts also provide lint/format; lint was not run here and format writes broadly, so do not use it as a read-only audit. No CI workflow or pytest configuration was found.

## Test responsibilities

| File | Principal coverage |
|---|---|
| backend/test_backend.py | canonical fixture ingestion, fields, search/price, legacy extraction, real chat, empty prompt, FastAPI TestClient |
| backend/test_chat_regressions.py | selected/named products, cart commands, wrong model action recovery, reference resolution, recommendations |
| backend/test_laya_contract.py | model identity, malformed decisions, unsupported actions, numeric distribution/confidence semantics |
| backend/test_chat_concurrency.py | blocked HTTP work yields to event loop; not throughput/load testing |
| backend/test_suggestions.py | context/output contracts, configured provider, failure without static fallback, catalog specification context |
| backend/test_suggestion_click.py | product-page question retains context; informational generation vs discovery |
| backend/test_search_budget_regressions.py | currency/budget/all-term Sony filtering |
| backend/test_accessory_compatibility.py | explicit connectors, manufacturer vs device, exact name under filters, stock/cart |
| backend/test_short_accessory.py | implicit device references, short S7 retention, contradictory filters, out-of-stock and Sony |
| frontend/tests/chat-cart.test.cjs | client mutation, stale quantities, lookup failure, conflicting markers, out-of-stock |
| frontend/tests/product-suggestions.test.cjs | validation, cache, concurrent deduplication, no fallback |
| frontend/tests/suggestion-click.test.cjs | original panel opens and submits once in hook harness |

evaluation/test_*.py are diagnostic scripts that may invoke external services; they are not automatically part of the documented regression suite.

## JEV methodology and provenance

Dataset: LocalLLaMA/typed-decisions, configuration all / test split. Local files: evaluation/jev_benchmark/dataset/typed_decisions_test.json and test-00000-of-00001.parquet. Fresh parsing confirms **400 cases, 2000 questions: 600 choice, 800 score, 600 noul**, across agent_trace_observability, customer_service, invoice_processing and security_incidents. JSON SHA-256: **46beeb91b458bc737baddb2fe333268bb038847eafc31e55e54aaf3e3553280b**. [Dataset evidence](handover_evidence_2026-10-10/dataset_verification.json).

A case is one HTTP request containing five questions. Case HTTP timings are not independent per-question inference timings. V2 runner's “decision latency” divides case latency by five. Sequential runs have no retries and 60-second request timeout where recorded. Gold score label accuracy differs from MAE against expected numeric score; noul uses binary classification. Probability Brier compares soft gold distributions; ECE bins confidence versus correctness. Installed choice confidence is entropy-derived, answer_confidence is distinct. Do not market ECE as calibrated correctness or generic accuracy as shopping/business accuracy.

runner.py scores successful decisions and excludes errors from metric cohorts; run_baseline_v2.py additionally records strict full-test and successful-only denominators and request provenance. Its model_configuration string is hardcoded to base Laya. Report generation also hardcodes ONNX identity and contains optimistic calibration text even when invoked on V2 or failed runs. Numeric raw outputs and actual loaded identity take precedence over narrative labels.

## Primary saved runs — freshly recounted, not rerun

| Run/source | Model/runtime; revision | Cases/decisions; correct | Choice / score / noul accuracy | Overall | Failed decisions | Mean / P50 / P95 case HTTP ms | MAE / soft Brier / ECE |
|---|---|---|---|---|---|---|---|
| B: baseline_v2_20261004_summary.json (finished **Oct 3 UTC**, despite filename) | convaiinnovations/laya; @receptron/laya 0.1.2 ONNX; immutable revision not attested | 400/2000; **718** | 28.8333% / 31.75% / 48.50% | 35.90% | 0 | 8847.84 / 9590.26 / 14133.02 | 0.690507 / 0.100405 / 0.153419 |
| S: specialist_summary.json (Oct 5) | convaiinnovations/laya-typed-decisions; same Node ONNX runtime, FP32 CPU; **1a793eb568e6718f15941d08f85432581df534e3** | 400/2000; **1530** | 73.1667% / 72.25% / 85.50% | 76.50% | 0 | 11641.46 / 12517.73 / 18004.62 | 0.247058 / 0.018859 / 0.417561 |
| V: jev_full_20261008T115135_157161Z (Oct 8) | Mass121/laya-typed-decisions-v2; Python CPU; **6fb41711ea5ff81097e6fc09ccebf31138b06e4d** attributed by runner/service evidence | 400/2000; **1576** | 75.50% / 75.25% / 86.83% rounded | 78.80% | 0 | 7874.12 / 8542.74 / 11390.68 | 0.2475 / 0.0269 / 0.1312 |

[B source](../evaluation/jev_benchmark/results/baseline_v2_20261004_summary.json), [S source](../evaluation/laya_specialist_onnx_isolated/benchmark/runs/20261005_184532_IST/specialist_summary.json), [V source](../laya_v2_service/results/jev_full_20261008T115135_157161Z/laya_jev_benchmark_summary.json). B/S are ignored local artifacts: links resolve in this workspace but **not in a fresh clone**. The [numeric inventory](handover_evidence_2026-10-10/benchmark_inventory.json) preserves their relevant provenance. [Fresh raw recount](handover_evidence_2026-10-10/benchmark_recount.json) independently reproduces the three correct counts and zero decision errors.

B→S gains 40.60 percentage points /812 correct, but mean HTTP latency increases 31.57% and ECE worsens. S→V gains 2.30 points /46 correct; different checkpoint/runtime runs are not a controlled production speed experiment. Hardware load, significance, training overlap and shopping generalization are unverified. V saved rows omit per-response model identity; do not describe loaded weight hashes as freshly verified.

Saved weights provenance: S weights SHA-256 4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e, ONNX e2b4eeeb1347a94680839a0bdcd473de53c151ab6134193c82ba525459c59474. V [model verification](../laya_v2_service/results/model_verification.json) records weights c10b666f708e0e3dfbc6e512bfe4bae0340dcdac2ff167f38137c50e1089071d. Loaded bytes were not rehashed in this task.

## Complete saved summary registry

Every discovered summary/cohort is separately indexed below; “—” means not recorded/not applicable, not zero. Additional numeric fields, runtime, coverage, failures, labels and provenance are in [benchmark_inventory.json](handover_evidence_2026-10-10/benchmark_inventory.json). Integration/validation summaries are not accuracy benchmark runs. Archived rollback copies are not independent experiments.

| Summary/cohort | Date recorded | Cases / decisions | Accuracy | Successful / failed |
|---|---|---|---|---|
| laya_v2_service/results/jev_validation_2026-10-08T103503963Z/laya_jev_benchmark_summary.json [summary] | 2026-10-08T10:35:25.340573+00:00 | 5 / 25 | 64.00% | 25 / 0 |
| laya_v2_service/results/jev_full_20261008T115135_157161Z/laya_jev_benchmark_summary.json [summary] | 2026-10-08T12:44:04.994148+00:00 | 400 / 2000 | 78.80% | 2000 / 0 |
| evaluation/results/summary_metrics_20261003_142229.json [summary] | 20261003_142229 | 58 / — | 67.24% | — / — |
| evaluation/results/summary_metrics_20261002_114453.json [summary] | 20261002_114453 | 58 / — | 67.24% | — / — |
| evaluation/results/summary_metrics_20261002_113946.json [summary] | 20261002_113946 | 58 / — | 67.24% | — / — |
| evaluation/results/summary_metrics.json [summary] | 20261003_142229 | 58 / — | 67.24% | — / — |
| evaluation/results/summary.json [summary] | 2026-10-02T09:11:30.061240+00:00 | 12 / — | — | — / — |
| evaluation/laya_specialist_onnx_isolated/python_validation_summary.json [summary] | not recorded; see path | — / — | — | — / — |
| evaluation/laya_specialist_onnx_isolated/node_validation_summary.json [summary] | not recorded; see path | — / — | — | — / — |
| evaluation/laya_specialist_onnx_isolated/integration/live_runs/20261005_210712_regression_fixes/validation_summary.json [summary] | not recorded; see path | — / — | — | — / — |
| evaluation/laya_specialist_onnx_isolated/integration/live_runs/20261005_205325/summary.json [summary] | not recorded; see path | — / — | — | — / — |
| evaluation/laya_specialist_onnx_isolated/integration/live_runs/20261005_205325/final_summary.json [summary] | not recorded; see path | — / — | — | — / — |
| evaluation/jev_benchmark/results/phase5_rollback_20261004/baseline_v2_20261004_summary.json [summary] | 2026-10-03T19:55:20.713389+00:00 | 400 / 2000 | 35.90% | 2000 / 0 |
| evaluation/jev_benchmark/results/phase5_optimized_typed_decisions_20261004_summary.json [summary] | 2026-10-04T14:03:37.177929+00:00 | 400 / 2000 | 76.60% | 2000 / 0 |
| evaluation/jev_benchmark/results/phase4_typed_decisions_candidate_20261004_pilot_summary.json [candidate] | 2026-10-04T09:01:16.726362+00:00 | 40 / 200 | 72.50% | 200 / 0 |
| evaluation/jev_benchmark/results/phase4_typed_decisions_candidate_20261004_pilot_summary.json [baseline_same_cases] | 2026-10-04T09:01:16.942374+00:00 | 40 / 200 | 33.50% | 200 / 0 |
| evaluation/jev_benchmark/results/phase4_typed_decisions_candidate_20261004_full_summary.json [candidate] | 2026-10-04T09:55:47.637347+00:00 | 400 / 2000 | 76.60% | 2000 / 0 |
| evaluation/jev_benchmark/results/phase4_typed_decisions_candidate_20261004_full_summary.json [baseline_same_cases] | 2026-10-04T09:55:47.778344+00:00 | 400 / 2000 | 35.90% | 2000 / 0 |
| evaluation/jev_benchmark/results/phase4_rollback_20261004/baseline_v2_20261004_summary.json [summary] | 2026-10-03T19:55:20.713389+00:00 | 400 / 2000 | 35.90% | 2000 / 0 |
| evaluation/jev_benchmark/results/PHASE3_REFERENCE_VALIDATION_summary.json [summary] | not recorded; see path | — / — | — | — / — |
| evaluation/jev_benchmark/results/laya_jev_benchmark_summary.json [summary] | 2026-10-08T10:31:00.988712+00:00 | 5 / 25 | 0.00% | 0 / 25 |
| evaluation/jev_benchmark/results/jev_verification_typed_decisions_20261004_summary.json [summary] | 2026-10-04T15:21:22.310342+00:00 | 400 / 2000 | 76.60% | 2000 / 0 |
| evaluation/jev_benchmark/results/baseline_v2_20261006_214159_summary.json [summary] | 2026-10-06T17:43:08.593992+00:00 | 400 / 2000 | 76.50% | 2000 / 0 |
| evaluation/jev_benchmark/results/baseline_v2_20261005_212216_summary.json [summary] | 2026-10-05T16:49:23.885275+00:00 | 400 / 2000 | 35.90% | 2000 / 0 |
| evaluation/jev_benchmark/results/baseline_v2_20261005_125336_summary.json [summary] | 2026-10-05T08:19:17.758113+00:00 | 400 / 2000 | 35.90% | 2000 / 0 |
| evaluation/jev_benchmark/results/baseline_v2_20261004_summary.json [summary] | 2026-10-03T19:55:20.713389+00:00 | 400 / 2000 | 35.90% | 2000 / 0 |
| evaluation/jev_benchmark/results/baseline_v2_20261004_rerun_summary.json [summary] | 2026-10-04T16:35:02.323914+00:00 | 400 / 2000 | 35.90% | 2000 / 0 |
| evaluation/laya_specialist_onnx_isolated/integration/runs/20261005_202712/summary.json [summary] | not recorded; see path | — / — | — | — / — |
| evaluation/laya_specialist_onnx_isolated/integration/runs/20261005_202453/summary.json [summary] | not recorded; see path | — / — | — | — / — |
| evaluation/laya_specialist_onnx_isolated/benchmark/runs/20261005_184532_IST/specialist_summary.json [summary] | 2026-10-05T14:33:22.154427+00:00 | 400 / 2000 | 76.50% | 2000 / 0 |

Other important artifacts: September 30 [Laya-vs-bypass CSV](../benchmark_results/laya_vs_bypass_2026-09-30.csv) predates current V2/catalog formatting and is not current latency evidence; October 8 [seven-query comparison](../laya_v2_service/results/comparison_20261008T063935_485312Z.json) is a two-service smoke test, not shopping accuracy. Phase-three reference validation partitions incorrect cases, rather than rerunning a full model benchmark. Model source preparation/training files are preserved experimental tools, not operations executed here.

## Discrepancies that must remain visible

- evaluation/jev_benchmark/results/laya_jev_benchmark_summary.json, Oct 8 10:31 UTC: five cases, **0 successful /25 failed** decisions before wrapper compatibility repair. Zero Brier/ECE reflects absent scored evidence, not perfection.
- V2 validation at Oct 8 10:35 UTC: five cases, 25 successful, 16 correct (64%); this small workflow subset is separate from full V2 78.80%.
- Phase-four Python Laya 0.3.26 specialist pilot: 145/200 (72.5%); full candidate:1532/2000 (76.6%), same specialist checkpoint. Phase-five optimized Python run likewise1532/2000. These differ from ONNX specialist1530/2000 and are not V2.
- Oct 4 typed-decisions verification and Oct 6 baseline-named run use hardcoded base labels despite specialist-like results (1532 and1530 correct). Loaded model must be established from their raw provenance; do not attribute them to base solely by filename/label.
- Pilot summary's expected_by_type incorrectly retains full 600/800/600 constants; use its per-cohort by_type or actual 200 rows, not those hardcoded totals.
- Saved Ragas summary at Oct 2 09:11 UTC contains **12 cases, 11 deterministic responses, one eligible Ollama response**, all four metrics scored 1/1 eligible (1/12 overall). Saved metrics: faithfulness1.0, relevancy0.751014, precision≈1.0, recall1.0. evaluation/README.md instead claims five eligible and averages0.8762/0.7225/0.8/0.9667; no matching current summary was found. Preserve the discrepancy rather than presenting its README as current evidence.
- Saved 58-query ShopAI summaries Oct2/3 report67.24% raw intent accuracy and different mean timings; model identity/revision is not attested in those summary files. They use custom shopping labels and heuristic grounding/retrieval, not JEV gold or current model certification.

## Benchmark execution commands and overwrite safety

The following commands are **derived, not executed for this handover**.

Current V2 HTTP benchmark from root:

```powershell
& ./.venv/Scripts/python.exe ./run_v2_jev.py
```

Uses existing local test JSON and current5056, writes a new timestamped results directory under laya_v2_service/results, 400 cases. Requires V2 healthy, does not import catalog/train model. Timestamped directories avoid normal baseline overwrite.

For a deliberately bounded V2 parity sample and new output directory, bypass runner CLI's stale5055 health preflight:

```powershell
& ./.venv/Scripts/python.exe -c "import sys; from pathlib import Path; from datetime import datetime,timezone; sys.path.insert(0,'evaluation/jev_benchmark'); from runner import check_laya_health,run_benchmark; check_laya_health('http://127.0.0.1:5056/health'); out=Path('laya_v2_service/results')/('handover_sample_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')); run_benchmark(dataset_path=Path('evaluation/jev_benchmark/dataset/typed_decisions_test.json'),limit=5,decide_url='http://127.0.0.1:5056/decide',results_dir=out)"
```

runner.py CLI offers --sample/--full/--workflow/--endpoint but calls default5055 health even when --endpoint is5056 and writes fixed default outputs; do not invoke it against saved baselines. run_baseline_v2.py --full also uses fixed baseline prefix/default5055 and can overwrite outputs. Historical specialist experiment command is stored in its summary and depends on ignored source/environment/bundle; not fresh-clone runnable.

laya_v2_service/run_benchmark.py runs the supplied in-process evaluator to a timestamped file but calls snapshot_download and dataset loading, potentially downloading models/dataset; it is not the HTTP JEV run and must only be used under separate approved provisioning. Supplied evaluate.py's default-device expression accesses missing laya.torch on this installed version; the wrapper avoids that issue. Hardcoded other-model comparison figures in supplied evaluator are reference numbers, not local measurements.

Custom shopping benchmarking supports --dataset, --repeatability-runs and --output-dir; choose a unique directory:

```powershell
& ./.venv/Scripts/python.exe ./evaluation/benchmark_runner.py --dataset ./evaluation/benchmark_dataset.json --output-dir ./evaluation/results/new_owner_review
```

It still overwrites fixed summary/report names within that chosen directory. Ragas evaluator --capture-only, --score-captured and --metrics are implemented, but **all use fixed evaluation/results paths**. Back up and isolate its outputs before any execution. It needs evaluation requirements, cloud judge key and optional embedding model; it is outside production chat and was not rerun here. Scrapers similarly overwrite expanded JSONL; they are not test commands.

## Source references and research integrity

[Runner](../evaluation/jev_benchmark/runner.py), [strict telemetry runner](../evaluation/jev_benchmark/run_baseline_v2.py), [metrics](../evaluation/jev_benchmark/metrics.py), [V2 wrapper](../run_v2_jev.py), [custom benchmark](../evaluation/benchmark_runner.py), [Ragas](../evaluation/evaluate.py), [prior detailed audit](shopai_stabilization_audit_2026-10-09.md), [evaluation inventory](handover_evidence_2026-10-10/additional_evaluation_inventory.json).

Freeze dataset/checkpoint/questions/adapter and record actual response identity, errors, coverage, hardware/load, cold/warm policy and output paths for future runs. Never merge these cohorts into one headline figure.
