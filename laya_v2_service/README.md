# Isolated Laya V2 service

Phase one only. All additions, dependencies, model cache, and results stay in this directory. No application switch was made. The existing port 5055 service, frontend, backend, Ollama, PostgreSQL, product search, and cart were not modified by this task. Earlier unrelated working-tree changes were preserved.

## Supplied files inspected

- laya_Model/infer.py: exact laya.load("Mass121/laya-typed-decisions-v2"), then agent.predict(state, questions).
- laya_Model/requirements.txt: supplied dependency baseline.
- laya_Model/evaluate.py: official LocalLLaMA/typed-decisions, configuration all, split test; calls laya.Agent and predicts typed questions.
- laya_Model/prepare_data.py: data preparation for training; not executed.
- laya_Model/train_ddp.py: training/checkpoint export; not executed. Its default base model does not replace infer.py's V2 checkpoint.

Also read laya_service/server.js to copy the shopping questions without changing it, and the installed laya/__init__.py and laya/agent.py to verify the runtime API.

The five supplied files are preserved in laya_Model. There were no trained weights in the ZIP.

## Verified model

Source: https://huggingface.co/Mass121/laya-typed-decisions-v2

Pinned revision: 6fb41711ea5ff81097e6fc09ccebf31138b06e4d

Downloaded checkpoint files: rl_agent_config.json, encoder/config.json, tokenizer/tokenizer.json, tokenizer/tokenizer_config.json, model.safetensors.

Weight size: 842,609,220 bytes. SHA-256: c10b666f708e0e3dfbc6e512bfe4bae0340dcdac2ff167f38137c50e1089071d.

Cache: .cache/huggingface (isolated from the existing model cache).

Verified on CPU using Python 3.13, Laya 0.4.0, Transformers 5.19.0, Torch 2.14.1. requirements.lock.txt records all installed versions.

The supplied billing example selected billing issue with probability 0.9996, confidence 0.9954, and answer_confidence 0.9996. These are separate fields from the actual model; confidence is not replaced with the selected probability. Full verification metadata is in results/model_verification.json.

## Installation (PowerShell, from project root)

```powershell
py -3.13 -m venv .\laya_v2_service\.venv
& .\laya_v2_service\.venv\Scripts\python.exe -m pip install -r .\laya_v2_service\requirements.txt -c .\laya_v2_service\requirements.lock.txt
```

The isolated environment is already installed in this workspace. Do not recreate it while the service is running. The root requirements include the unchanged supplied baseline; the HTTP server uses Python's standard library.

## Start and test

```powershell
& .\laya_v2_service\.venv\Scripts\python.exe -u .\laya_v2_service\service.py
```

One process loads the pinned model once on CPU, then listens only on 127.0.0.1:5056. Startup failure exits with the exact exception; there is no old-model fallback. Use one instance. Stop it with Ctrl+C. Predictions share a lock to avoid concurrent forward passes.

In another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:5056/health
$payload = Get-Content -Raw -Encoding UTF8 .\laya_v2_service\example_request.json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5056/decide -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($payload)) | ConvertTo-Json -Depth 30
```

Request: JSON object containing state and non-empty questions objects exactly as infer.py expects. Choice, noul and score question types are accepted. No implicit question defaults. Missing/invalid input returns HTTP 400; inference failures return HTTP 500 with error_type and the real error.

Response: model, revision, latency_ms, raw (unaltered Laya output), choices (choice/probabilities/confidence for each choice question), and shopai. Missing confidence/probabilities remain null. latency_ms measures inference plus lock waiting, excluding startup/download and HTTP transport.

Health returns status=ok, model=Mass121/laya-typed-decisions-v2, loaded=true and the pinned revision. The listener starts only after model loading succeeds.

## Adapter and future integration boundary

shopai contains answers, decision, confidence, probabilities, model, and source=laya-python-v2 when answers.intent is a genuine choice in the six ShopAI categories: product_search, recommendation, product_details, add_to_cart, cart_action, general_query. The typed model chooses among the criteria in the request. shopai_questions.json contains the existing shopping questions copied for testing.

For other question IDs/categories (including the billing example), shopai is null and raw remains available. No keyword fallback, invented confidence, or arbitrary remapping is used. All seven shopping results produced the expected adapter structure.

No backend/orchestrator wiring was added. An eventual separately authorized integration must consume shopai and review existing source/model verification guards; this adapter does not impersonate the old ONNX source.

## Comparison smoke test

Keep the existing service on 5055 and V2 on 5056 running, then:

```powershell
$env:PYTHONIOENCODING = 'utf-8'
& .\laya_v2_service\.venv\Scripts\python.exe .\laya_v2_service\compare_services.py
```

Both ports receive identical state.message and questions. Each run saves a new timestamped JSON under results, using exclusive creation. Full raw outputs, probabilities, confidence, output structures, and HTTP request latency are retained. Neither service is modified or restarted by this script.

Measured run: results/comparison_20261008T063935_485312Z.json. All 14 requests returned HTTP 200; both services selected the same categories in all seven cases.

| Input | Choice (both services) | Confidence 5055 / 5056 | HTTP ms 5055 / 5056 |
| --- | --- | --- | --- |
| Show me Samsung phones under ₹20000 | product_search | 0.3536 / 0.9841 | 8351.7 / 4790.9 |
| Recommend a good phone for gaming | recommendation | 0.5927 / 0.9925 | 4677.3 / 3848.6 |
| Tell me the price of this product | product_details | 0.1372 / 0.6600 | 2958.8 / 2223.3 |
| Add this phone to cart | add_to_cart | 0.5821 / 0.9894 | 2865.1 / 2347.6 |
| Show my cart | cart_action | 0.4691 / 0.9664 | 2867.8 / 2187.6 |
| Which phone has the best camera? | recommendation | 0.3868 / 0.9672 | 3180.8 / 2944.3 |
| Hello | general_query | 0.2285 / 0.9507 | 3032.0 / 2026.6 |

These are single sequential requests with different runtimes/models and no formal warmup or statistical latency study. Higher confidence is not evidence of greater accuracy or calibration. This is an integration smoke test, not a ShopAI accuracy benchmark.

Output structure: 5055 returns top-level answers/usage and ONNX identity metadata; 5056 wraps the genuine answers/usage in raw and adds explicit model/revision, choices, adapter, and measured inference latency. See the JSON for all keys and probability distributions.

## Official benchmark (not executed)

The supplied evaluate.py evaluates the LocalLLaMA/typed-decisions all/test split and reports typed choice/noul/score metrics: accuracy, soft accuracy, Brier, ECE, KL, total variation, score MAE, within-one-level, per-workflow metrics, and latency percentiles. Its other-model comparison figures are hard-coded reference numbers, not fresh measurements. Its decision count assumes five questions per case; review that assumption when interpreting reports.

The supplied CLI accesses laya.torch in the default-device expression, which Laya 0.4 does not expose; even passing --device cannot bypass evaluation of that default. run_benchmark.py calls the supplied evaluate_model function directly with device=cpu and the pinned downloaded V2 snapshot, preserving the original script.

```powershell
& .\laya_v2_service\.venv\Scripts\python.exe .\laya_v2_service\run_benchmark.py
```

This downloads the official test dataset if necessary and writes a new results/benchmark_<UTC timestamp>.json. It refuses an existing target and does not use the original benchmark_report.json default. Network access is needed on the first dataset download. No training or retraining occurs. The benchmark was not run during this phase.

## Validation and blockers

Exact checkpoint loading, the supplied billing request over HTTP, health, all seven comparison inputs, adapter outputs, invalid-input HTTP 400, Python compilation, and pip dependency checks passed. The old 5055 health still reports its original convaiinnovations/laya-typed-decisions model, loaded=true, fallback=false.

Initial sandbox networking blocked package installation; the authorized network path resolved that setup issue. There are no remaining phase-one blockers. Both services remained separate. The official benchmark remains unexecuted as requested.
