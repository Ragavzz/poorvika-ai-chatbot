# ShopAI Ragas evaluation

Ragas is an evaluation framework for checking answers from retrieval augmented generation systems. It runs here as an offline evaluation tool, not as part of a customer request.

## How it fits ShopAI

The production request path remains React → FastAPI `/api/chat` → Laya → PostgreSQL product search → Ollama → response. The evaluation script imports the existing `ChatService` and runs each question through `generate_response`. It observes that service instance's actual Laya decision, database search results and Ollama input/output without modifying the production service or API contract. If generation does not happen or Ollama fails, the row is retained with `evaluation_status`, `error`, the actual ChatService return value, and the captured decision/search trace; it is excluded from Ragas scoring. Read-only diagnostic searches explain whether alternate catalog filters would have matched, but are never passed to ChatService or recorded as retrieved context.

The reference contexts used for context recall come from a second query to the same live database, with the exact same search filters and a larger result limit. The captured production retrieval remains the original top-five result. No catalog details or responses are fabricated. The dataset contains 12 realistic questions and no static answers.

## Metrics

- **Faithfulness**: whether claims in the answer are supported by retrieved product context.
- **Answer relevancy**: whether the answer addresses the user's question. This metric also needs embeddings.
- **Context precision**: whether the retrieved contexts are relevant to the question.
- **Context recall**: whether the production retrieval includes relevant catalog details from a broader same-filter database reference. Rows without reference data are not scored.

Ragas 0.4 collections metrics are used. The evaluator sends judge requests directly to Ollama Cloud's OpenAI-compatible API (`https://ollama.com/v1`) using `OLLAMA_API_KEY`; it defaults to `gpt-oss:20b-cloud`. Embeddings default to the local OpenAI-compatible Ollama endpoint (`http://localhost:11434/v1`) using `nomic-embed-text`. Pull the embedding model once with `ollama pull nomic-embed-text` if needed. Change `RAGAS_OLLAMA_MODEL` to select another available evaluator model, `RAGAS_OLLAMA_BASE_URL` to override the judge endpoint, or `RAGAS_OLLAMA_EMBEDDING_BASE_URL` to override the embedding endpoint.

## Run

1. Start PostgreSQL (or the application's documented SQLite catalog fallback), the Laya service, and Ollama. Ensure the chatbot model is available.
2. From the repository root, install evaluation-only dependencies into the active Python environment:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r evaluation\requirements.txt
   ```

3. Run:

   ```powershell
   .\.venv\Scripts\python.exe evaluation\evaluate.py
   ```

Set `RAGAS_OLLAMA_BASE_URL`, `RAGAS_OLLAMA_MODEL`, or `RAGAS_OLLAMA_EMBEDDING_MODEL` to override evaluator defaults. `backend/requirements.txt` and the production requirements are unchanged.

To rescore the actual responses already captured in the result JSON without sending the chat questions through ShopAI again, add `--score-captured`. You may also select metrics with `--metrics context_recall`. The normal command attempts all four metrics; unsupported outputs, judge failures, and missing reference data remain blank and are counted as unavailable in the summary.

## Results

The script writes raw ShopAI observations to `results/chat_responses.json`. It writes those same cases with per-row Ragas scores to `results/ragas_results.csv` and `results/ragas_results.json`, plus metric averages, scored row counts, and coverage to `results/summary.json`. Metric failures and unavailable data are left blank and recorded; averages include only finite numeric Ragas scores. `--capture-only` refreshes raw pipeline observations without scoring; `--score-captured` scores the saved observations without rerunning ShopAI. The results directory contains outputs of actual runs, not sample scores.

In the verified 12-question run, 5 questions reached Ollama and all four metrics scored those 5 responses. The other 7 were marked `failed_before_generation`: Laya chose `cart_action` for the power-bank and Apple-accessory discovery questions, and five actual product searches returned no rows. Diagnostics showed that the mobile-accessories request was filtered as `Smartphones`, and that the Samsung-products query term `products` suppressed otherwise available Samsung rows. Two other exact catalog filters (Samsung phones under ₹30,000 and laptops under ₹50,000) had no matches; the under-₹20,000 smartphone filter also had none. These findings are captured without changing live behavior.

Most recent verified averages (each metric scored 5/5 eligible responses): faithfulness 0.8762, answer relevancy 0.7225, context precision 0.8000, and context recall 0.9667. See `results/summary.json` for full precision and row counts.

## JEV scan

No active JEV implementation, dependency, configuration, API call, service, environment variable, or JEV-related file was found. Search hits were only incidental `jev` character sequences in package-lock integrity hashes. Nothing was removed.

## Production isolation

Ragas is only imported by this standalone script. The FastAPI app does not import the `evaluation` directory, and Ragas does not run during normal `/api/chat` requests.
