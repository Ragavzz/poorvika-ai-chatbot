# Mobile commerce frontend

## Goal
Recreate the requested React storefront in this blank TanStack project, using the selected frosted retail clarity direction and a familiar Indian electronics-shopping structure without copying Poorvika branding or assets.

## Build
- Create a responsive shared storefront shell with neutral “Mobile Mart” branding, search, account/cart actions, category navigation, and mobile navigation.
- Add the home page, product listing/search/filter experience, and dynamic product details page.
- Build reusable storefront parts for the navigation, search, categories, products, filters, details, and floating chatbot.
- Use bundled, original product-style artwork and a red, charcoal, white, and warm-neutral retail palette.
- Keep chatbot history in memory for the current browser session only.

## Backend boundary
- Centralize all remote calls in `src/services/api.ts`, configured by `VITE_API_BASE_URL`.
- Support `GET /api/products`, `GET /api/products/{id}`, `GET /api/products/search`, and `POST /api/chat`.
- Do not add a database, server backend, or product/chat intelligence to the frontend.
- Show graceful empty/error states when the FastAPI backend is unavailable; no final hardcoded product catalog.

## Routes
- `/` — home and discovery
- `/products` — search, filters, sorting, and product grid
- `/products/$productId` — product details and specifications

## Validation
- Verify desktop and mobile layouts, navigation, filters, product loading states, detail routing, and chatbot request/error handling.
- Ensure each page has unique metadata and the project remains locally downloadable with `.env.example` setup notes.
