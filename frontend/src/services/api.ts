export type Product = {
  id: string | number;
  name: string;
  brand?: string;
  price: number;
  originalPrice?: number;
  discount?: number;
  image?: string;
  images?: string[];
  category?: string;
  rating?: number;
  reviewCount?: number;
  inStock?: boolean;
  stock?: number;
  description?: string;
  specifications?:
    Record<string, string | number> | Array<{ label: string; value: string | number }>;
};

export type ProductQuery = {
  query?: string;
  category?: string;
  brand?: string[];
  minPrice?: number;
  maxPrice?: number;
  inStockOnly?: boolean;
  minRating?: number;
  minDiscount?: number;
  sort?: string;
  limit?: number;
  offset?: number;
};

const baseUrl = (import.meta.env["VITE_API_BASE_URL"] ?? "").replace(/\/$/, "");

const buildUrl = (
  path: string,
  query?: Record<string, string | number | boolean | string[] | undefined>,
) => {
  const url = `${baseUrl}${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === "" || (Array.isArray(value) && value.length === 0)) return;
    if (Array.isArray(value)) value.forEach((item) => params.append(key, item));
    else params.set(key, String(value));
  });
  const search = params.toString();
  return search ? `${url}?${search}` : url;
};

const request = async <T>(
  path: string,
  options?: RequestInit,
  query?: Record<string, string | number | boolean | string[] | undefined>,
  onResponse?: (response: Response) => void,
): Promise<T> => {
  if (!baseUrl) throw new Error("Connect your FastAPI backend by setting VITE_API_BASE_URL.");
  const response = await fetch(buildUrl(path, query), {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  onResponse?.(response);
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: string;
      message?: string;
    } | null;
    throw new Error(body?.detail ?? body?.message ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
};

const normalizeProducts = (payload: Product[] | { products?: Product[]; items?: Product[] }) =>
  Array.isArray(payload) ? payload : (payload.products ?? payload.items ?? []);

export const api = {
  getChatCapabilities(signal?: AbortSignal) {
    return request<{ ollama_enabled: boolean; model_configuration: string; timeout_ms: number }>(
      "/api/chat/suggestion-capabilities",
      { signal: AbortSignal.any([AbortSignal.timeout(8000), ...(signal ? [signal] : [])]) },
    );
  },
  async getProducts(query: ProductQuery = {}, signal?: AbortSignal) {
    const payload = await request<Product[] | { products?: Product[]; items?: Product[] }>(
      "/api/products",
      signal ? { signal } : undefined,
      {
        category: query.category,
        brand: query.brand,
        min_price: query.minPrice,
        max_price: query.maxPrice,
        in_stock_only: query.inStockOnly,
        min_rating: query.minRating,
        min_discount: query.minDiscount,
        sort: query.sort,
        limit: query.limit,
        offset: query.offset,
      },
    );
    return normalizeProducts(payload);
  },
  async searchProducts(query: ProductQuery, signal?: AbortSignal) {
    const payload = await request<Product[] | { products?: Product[]; items?: Product[] }>(
      "/api/products/search",
      signal ? { signal } : undefined,
      {
        q: query.query,
        category: query.category,
        brand: query.brand,
        min_price: query.minPrice,
        max_price: query.maxPrice,
        in_stock_only: query.inStockOnly,
        min_rating: query.minRating,
        min_discount: query.minDiscount,
        sort: query.sort,
        limit: query.limit,
        offset: query.offset,
      },
    );
    return normalizeProducts(payload);
  },
  getProduct(id: string, signal?: AbortSignal) {
    return request<Product>(
      `/api/products/${encodeURIComponent(id)}`,
      signal ? { signal } : undefined,
    );
  },
  getChatSuggestions(
    product: Partial<Product> & { name: string },
    onTiming?: (timings: Record<string, string | number>) => void,
    options?: { signal?: AbortSignal; requestId?: string },
  ) {
    return request<{ suggestions: string[] }>(
      "/api/chat/suggestions",
      {
        method: "POST",
        body: JSON.stringify({ product }),
        signal: options?.signal,
        headers: options?.requestId ? { "X-ShopAI-Request-ID": options.requestId } : {},
      },
      undefined,
      (response) => {
        const header = response.headers.get("X-ShopAI-Suggestion-Timing");
        if (header && onTiming) {
          try {
            onTiming(JSON.parse(header));
          } catch {
            /* Diagnostics never interrupt suggestions. */
          }
        }
      },
    );
  },
  async chat(message: string) {
    const payload = await request<{ response?: string; message?: string; reply?: string }>(
      "/api/chat",
      {
        method: "POST",
        body: JSON.stringify({ message }),
      },
    );
    const reply = payload.response ?? payload.reply ?? payload.message;
    if (!reply?.trim()) throw new Error("Empty response from chat service");
    return reply;
  },
};
