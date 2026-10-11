import { beginSuggestionTiming, recordSuggestionTiming } from "@/lib/suggestion-timing";
import { api, type Product } from "@/services/api";

export function getProductSuggestionContext(
  search: { q?: unknown; category?: unknown; products?: Product[]; filters?: unknown },
  product?: Product,
) {
  const clean = (value: unknown) =>
    typeof value === "string" ? value.trim().replace(/\s+/g, " ").slice(0, 120) : "";
  const query = clean(search.q);
  const category = clean(search.category);
  const name = clean(product?.name);
  if (Array.isArray(search.products) && search.products.length === 0) return null;
  if (product && (!name || !product.id || !Number.isFinite(product.price))) return null;
  if (!name && !query && !category) return null;
  const results = (search.products ?? []).slice(0, 8).map((item) => ({
    id: String(item.id),
    name: clean(item.name).slice(0, 180),
    ...(item.brand ? { brand: clean(item.brand).slice(0, 100) } : {}),
    ...(item.category ? { category: clean(item.category).slice(0, 100) } : {}),
    price: item.price,
    ...(item.specifications ? { specifications: item.specifications } : {}),
  }));
  const payload = name && product
    ? {
        id: String(product.id),
        name: product.name.slice(0, 300),
        ...(product.brand ? { brand: product.brand.slice(0, 150) } : {}),
        ...(product.category ? { category: product.category.slice(0, 150) } : {}),
        price: product.price,
        ...(product.description ? { description: product.description.slice(0, 4000) } : {}),
        ...(product.specifications ? { specifications: product.specifications } : {}),
      }
    : {
        name: query || category || "All products",
        ...(category ? { category } : {}),
        ...(query ? { query } : {}),
        ...(search.filters ? { filters: search.filters } : {}),
        products: results,
      };
  const key = (name ? "product:" : "catalog:") +
    JSON.stringify({ payload, prompt: "questions-v13" });
  return {
    key,
    title: name
      ? "Need help with " + name + "?"
      : "Need help choosing " + (query || category || "a product") + "?",
    product: payload,
  };
}

export function getSuggestionQueryKey(
  context: NonNullable<ReturnType<typeof getProductSuggestionContext>>,
  modelConfiguration?: string,
) {
  return ["model-product-suggestions-v3", context.key, context.product, modelConfiguration];
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
  signal?: AbortSignal,
  timeoutMs = 53000,
) {
  const initialId = beginSuggestionTiming(context.key);
  const controller = new AbortController();
  const cancel = () => controller.abort(signal?.reason);
  if (signal?.aborted) cancel();
  signal?.addEventListener("abort", cancel, { once: true });
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const requestId = recordSuggestionTiming(context.key, "frontend_request_started") ?? initialId;
  try {
    const response = await api.getChatSuggestions(
      context.product,
      (timings) => recordSuggestionTiming(context.key, "backend_completed", timings),
      { signal: controller.signal, requestId },
    );
    recordSuggestionTiming(context.key, "frontend_received");
    const questions = validateSuggestions(response.suggestions);
    recordSuggestionTiming(context.key, "success");
    return questions;
  } catch (error) {
    recordSuggestionTiming(
      context.key,
      timedOut || (error instanceof Error && /timeout|timed out/i.test(error.message))
        ? "timeout"
        : signal?.aborted
          ? "cancelled"
          : "failure",
      {
        reason: error instanceof Error ? error.message : String(error),
      },
    );
    if (timedOut) throw new Error("Suggestion generation timed out");
    throw error;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", cancel);
  }
}
