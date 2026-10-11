# API reference

[Main handover](FINAL_PROJECT_HANDOVER.md) · [Architecture](ARCHITECTURE.md)

Derived from route definitions, serializers and schemas, cross-checked against live [OpenAPI JSON](handover_evidence_2026-10-10/openapi.json) on 10 October 2026. Development base: http://127.0.0.1:8000. Frontend uses VITE_API_BASE_URL. No authentication dependency protects these application routes.

## Registered routes

| Method | Path | Purpose | OpenAPI codes |
|---|---|---|---|
| GET | / | Root | 200 |
| GET | /api/health | Health Check | 200 |
| GET | /api/products | Get Products | 200, 422 |
| GET | /api/products/search | Search Products | 200, 422 |
| GET | /api/products/{product_id} | Get Product | 200, 422 |
| POST | /api/products/ingest | Trigger Ingest | 200 |
| GET | /api/categories | Get Categories | 200 |
| GET | /api/brands | Get Brands | 200 |
| POST | /api/chat | Chat | 200, 422 |
| POST | /api/chat/suggestions | Suggestions | 200, 422 |

FastAPI also registers GET /openapi.json, /docs, /docs/oauth2-redirect and /redoc for schema/documentation. Source-defined additional outcomes below are not all declared in OpenAPI.

## Health

GET /: no input; {status:online, service:APP_NAME, framework:FastAPI, docs_url:/docs}.

GET /api/health: no input; {status:healthy|degraded, service, database:{type,connected,details,product_count}}. Checks database only, not Laya/Ollama; returns 200 even when degraded. SQLite fallback can appear healthy: inspect database.type. A failing primary connection can trigger fallback creation/ingestion, so this check is not universally free of disk writes.

## Product list/search

GET /api/products returns an array, not ProductListResponse. GET /api/products/search returns the same array and adds q. Parameters below apply to both, except q:

| Parameter | Type | Default | Bounds / usage |
|---|---|---|---|
| q | string | none |  |
| category | string | none |  |
| brand | array | none | repeat key for multiple brands |
| min_price | number | none |  |
| max_price | number | none |  |
| in_stock_only | boolean | false |  |
| min_rating | number | none | minimum 0; maximum 5 |
| min_discount | number | none | minimum 0; maximum 100 |
| sort | string | none |  |
| limit | integer | 50 | minimum 1; maximum 100 |
| offset | integer | 0 | minimum 0 |

Sort: price_asc, price_desc, rating/rating_desc, discount/discount_desc; unrecognized values use default ordering. Multiple brands are ORed; common constraints are ANDed. Known category aliases map to stored categories; unknown categories match category **or name**. Empty/all category suppresses category filtering. Price/rating/discount tool predicates apply only for positive values; zero does not enforce a bound. Route price fields have no explicit nonnegative constraint.

q uses normalized all-term ILIKE substring matching across name/brand/category/model/description, not vector search or PostgreSQL full-text indexing. exact_name is an internal tool argument, not an API parameter.

Actual list/search fields:

```text
id:string, name:string, brand:string, price:number,
originalPrice:number|null, discount:number, image:string|null,
images:array, category:string, rating:number|null, reviewCount:integer,
inStock:boolean, specifications:object (first two flattened entries)
```

There is no total count or description in this optimized list path. Product routes do not bind response_model=ProductOut: the more expansive ProductOut/ProductListResponse declarations are not the wire contract.

GET /api/products/{product_id}: string ID; basic fields above plus description and **all** flattened specifications. Exact stock quantity is not serialized. Missing ID ->404 {detail:string}. Query validation ->422; get_db ->503 when primary and fallback both fail; unexpected database/query exceptions can give 500.

GET /api/categories and /api/brands: no input; sorted nonempty distinct string arrays. Both use get_db (possible 503/500). There is no categories table.

POST /api/products/ingest: no body; configured JSONL upsert using run_dataset_ingestion. Returns {status:success,message:string}; failure ->500 {detail:string}. Creates missing tables and commits writes; no admin/token gate. **Not executed for this handover.**

## Chat

POST /api/chat:

```json
{"message":"Show me Sony earphones under 1000 rupees"}
```

Required message:string; no schema length maximum. Empty/whitespace ->200 with guidance. Normal response and controlled model failure both use {response:string}. Missing/malformed body ->422; DB/fallback unavailable ->503; unhandled orchestration ->500. No history array, session ID, separate cart field or streaming schema.

React appends two newlines and this trailing convention inside message:

```text
<shopai_client_context>{"recent_product_ids":[],"cart":[]}</shopai_client_context>
```

Cart entries contain id/name/price/quantity; suggestion clicks may include suggestion_product_id. Values are client-supplied and incompletely typed. Context is removed before Laya; full prior turns are not submitted.

Response conventions: SHOPAI_PRODUCTS records recent IDs, SHOPAI_ADD_TO_CART contains one ID, SHOPAI_CART_ACTION contains action/product_id/expected_quantity/quantity JSON. The frontend executes guarded client mutations; there is no order backend.

## Generated related questions

POST /api/chat/suggestions: {product:SuggestionProduct}.

| Product field | Contract |
|---|---|
| name | Required string, 1–300 chars; trimmed; blank rejected |
| brand/category | Optional nullable strings, <=150 chars |
| price | Optional nullable finite number >=0 |
| description | Optional nullable string <=4000 chars |
| specifications | Optional nullable dict of string/int/float values or list of such dicts; <=80 entries and JSON length <=12000 |

Returns {suggestions:[string,...]}, exactly 3 or 4 unique normalized questions, each 10–240 chars ending in ?. Invalid request ->422; provider/malformed generation failure ->503 {detail:"Suggestions are unavailable"}. No static fallback.

This endpoint does not authenticate or retrieve the supplied context from the database. Product-page data comes from frontend catalog cache; listing data is a query/category label. Timing headers: Server-Timing, X-ShopAI-Suggestion-Timing and Access-Control-Expose-Headers. They exclude upstream queue/network delay.

## Python Laya V2 — separate port 5056

GET /health returns status=ok, model=Mass121/laya-typed-decisions-v2, revision=6fb41711ea5ff81097e6fc09ccebf31138b06e4d, loaded=true.

POST /decide requires {state:object,questions:nonempty object}; Content-Length 1–1000000 bytes; each question must define choice, score or noul. Model library handles remaining definition semantics. Backend supplies state.message and [shopping questions](../laya_v2_service/shopai_questions.json). Response: model, revision, latency_ms, raw, answers, choices, shopai (nullable shopping adapter). Backend consumes answers.intent. Invalid input ->400, inference ->500 with error/error_type/model, unknown path ->404. No TLS/auth/streaming/model fallback; loopback bind only.

Client validates model ID, object structure, allowlisted choice, finite [0,1] confidence, exact six probability keys and sum tolerance 0.001. answer_confidence/action remain separate. Revision is not enforced; escalation/action metadata does not govern execution. Entropy-derived choice confidence is not calibrated correctness.

## Legacy ONNX contracts

laya_service/server.js: GET /health returns status/service/model/laya_loaded/loading. POST /decide accepts state and optional questions (default shopping questions), returns actual systemOne output **or fabricated keyword fallback confidence/probabilities**, generally 200. Malformed JSON ->400, unknown path ->404, OPTIONS ->204. PORT defaults 5055; wildcard CORS; no explicit interface bind. Current backend model guard rejects this service.

switchable_server.mjs imports ignored evaluation/laya_specialist_onnx_isolated/integration/service.mjs, default port 5056, LAYA_MODEL=base|specialist. Historical specialist has health/decide with no inference fallback; its required code/bundle is absent from a clean Git checkout. It must not compete with Python V2. Its old backend integration instructions do not satisfy the current V2 identity guard.

## Source references

[Product routes](../backend/app/routes/products.py), [health](../backend/app/routes/health.py), [chat](../backend/app/routes/chat.py), [suggestions](../backend/app/routes/suggestions.py), [schemas](../backend/app/schemas/suggestions.py), [product serializer](../backend/app/models/product.py), [tool](../backend/app/tools/product_search_tool.py), [V2](../laya_v2_service/service.py).
