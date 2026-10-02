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

const buildUrl = (path: string, query?: Record<string, string | number | boolean | string[] | undefined>) => {
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
): Promise<T> => {
  if (!baseUrl) throw new Error("Connect your FastAPI backend by setting VITE_API_BASE_URL.");
  const response = await fetch(buildUrl(path, query), {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
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
    return request<Product>(`/api/products/${encodeURIComponent(id)}`, signal ? { signal } : undefined);
  },
  async chat(message: string) {
    const payload = await request<{ response?: string; message?: string; reply?: string }>(
      "/api/chat",
      {
        method: "POST",
        body: JSON.stringify({ message }),
      },
    );
    return (
      payload.response ??
      payload.reply ??
      payload.message ??
      "I received your message, but the response was empty."
    );
  },
};
