import { recordSuggestionTiming } from "@/lib/suggestion-timing";
import { api, type Product } from "@/services/api";

export function getProductSuggestionContext(
  search: { q?: unknown; category?: unknown },
  product?: Product,
) {
  const clean = (value: unknown) =>
    typeof value === "string" ? value.trim().replace(/\s+/g, " ").slice(0, 120) : "";
  const query = clean(search.q);
  const category = clean(search.category);
  const name = clean(product?.name);
  if (!name && !query && !category) return null;
  const key = name
    ? "product:" + product?.id
    : "catalog:" + query.toLowerCase() + ":" + category.toLowerCase();
  const payload =
    name && product
      ? {
          name: product.name.slice(0, 300),
          ...(product.brand ? { brand: product.brand.slice(0, 150) } : {}),
          ...(product.category ? { category: product.category.slice(0, 150) } : {}),
          price: product.price,
          ...(product.description ? { description: product.description.slice(0, 4000) } : {}),
          ...(product.specifications ? { specifications: product.specifications } : {}),
        }
      : { name: query || category, ...(category ? { category } : {}) };
  return {
    key,
    title: name
      ? "Need help with " + name + "?"
      : "Need help choosing " + (query || category) + "?",
    product: payload,
  };
}

function validateSuggestions(value: unknown): string[] {
  if (
    !Array.isArray(value) ||
    value.length < 3 ||
    value.length > 4 ||
    value.some((item) => typeof item !== "string")
  )
    throw new Error("Invalid generated suggestions");
  const questions = (value as string[]).map((text) => text.trim().replace(/\s+/g, " "));
  if (
    questions.some((text) => text.length < 10 || text.length > 240 || !text.endsWith("?")) ||
    new Set(questions.map((text) => text.toLowerCase())).size !== questions.length
  )
    throw new Error("Invalid generated suggestions");
  return questions;
}

export async function getProductSuggestions(
  context: NonNullable<ReturnType<typeof getProductSuggestionContext>>,
) {
  const storageKey = "shopai:llm-suggestions:v1:" + context.key;
  // Successful results survive refreshes in this tab; unavailable storage is harmless.
  try {
    const cached = sessionStorage.getItem(storageKey);
    if (cached) { recordSuggestionTiming(context.key, "cache_hit"); return validateSuggestions(JSON.parse(cached)); }
  } catch {
    /* Request fresh LLM output if the cached value is unusable. */
  }
  recordSuggestionTiming(context.key, "frontend_request_started");
  const response = await api.getChatSuggestions(context.product, (timings) => recordSuggestionTiming(context.key, "backend_completed", timings));
  recordSuggestionTiming(context.key, "frontend_received");
  const questions = validateSuggestions(response.suggestions);
  try {
    sessionStorage.setItem(storageKey, JSON.stringify(questions));
  } catch {
    /* React Query still caches this session. */
  }
  return questions;
}
