# Mobile Mart frontend

A React 19 + TanStack Start ecommerce frontend prepared for a Python FastAPI backend.

## Local setup

```bash
bun install
cp .env.example .env
bun run dev
```

Set `VITE_API_BASE_URL` in `.env` to your FastAPI server URL.

## Expected API

- `GET /api/products`
- `GET /api/products/{id}`
- `GET /api/products/search?q=...`
- `POST /api/chat` with `{ "message": "..." }`

The frontend contains no product database, chatbot model, or Node/Express backend. Product pages show a connection state until the configured API responds.
