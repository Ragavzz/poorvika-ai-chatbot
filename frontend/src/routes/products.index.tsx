import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { ChevronRight, Home, SlidersHorizontal, X } from "lucide-react";
import { useState } from "react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { ProductFilters } from "@/components/storefront/ProductFilters";
import { ProductGrid } from "@/components/storefront/ProductGrid";
import { api } from "@/services/api";

const searchSchema = z.object({
  q: z.string().optional(),
  category: z.string().optional(),
  sort: z.string().optional(),
  page: z.coerce.number().int().min(1).optional(),
});

export const Route = createFileRoute("/products/")({
  validateSearch: searchSchema,
  head: () => ({
    meta: [
      { title: "Electronics Catalog — ShopTech Marketplace" },
      {
        name: "description",
        content: "Explore genuine electronics, earphones, chargers, smartwatches, and appliances.",
      },
      { property: "og:title", content: "Electronics Catalog — ShopTech Marketplace" },
      {
        property: "og:description",
        content: "Shop authentic electronics with warranty and fastest doorstep delivery.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: ProductsPage,
});

const sortOptions = [
  { label: "Most Relevant", value: "" },
  { label: "Top Reviews", value: "rating_desc" },
  { label: "Price: High to Low", value: "price_desc" },
  { label: "Price: Low to High", value: "price_asc" },
  { label: "Best Discount", value: "discount_desc" },
];
const PAGE_SIZE = 24;

function ProductsPage() {
  const search = Route.useSearch();
  const navigate = useNavigate({ from: "/products/" });
  const page = search.page ?? 1;

  // Filter states
  const [maxPrice, setMaxPriceState] = useState(150000);
  const [inStockOnly, setInStockOnly] = useState(false);
  const [selectedBrands, setSelectedBrands] = useState<string[]>([]);
  const [minRating, setMinRating] = useState(0);
  const [minDiscount, setMinDiscount] = useState(0);
  const [mobileFilters, setMobileFilters] = useState(false);

  const resetPage = () => {
    if (page > 1) void navigate({ search: (previous) => ({ ...previous, page: undefined }) });
  };
  const setPage = (nextPage: number) =>
    void navigate({ search: (previous) => ({ ...previous, page: nextPage > 1 ? nextPage : undefined }) });
  const setMaxPrice = (value: number) => {
    resetPage();
    setMaxPriceState(value);
  };

  const requestQuery = {
    ...(maxPrice < 150000 ? { maxPrice } : {}),
    inStockOnly,
    minRating,
    minDiscount,
    ...(selectedBrands.length > 0 ? { brand: selectedBrands } : {}),
    ...(search.category ? { category: search.category } : {}),
    ...(search.sort ? { sort: search.sort } : {}),
    limit: PAGE_SIZE + 1,
    offset: (page - 1) * PAGE_SIZE,
  };

  const query = useQuery({
    queryKey: [
      "products",
      search.q,
      search.category,
      search.sort,
      maxPrice,
      inStockOnly,
      minRating,
      minDiscount,
      [...selectedBrands].sort(),
      page,
    ],
    queryFn: ({ signal }) =>
      search.q
        ? api.searchProducts({ ...requestQuery, query: search.q }, signal)
        : api.getProducts(requestQuery, signal),
    retry: false,
  });

  const hasNextPage = (query.data?.length ?? 0) > PAGE_SIZE;
  const filteredProducts = (query.data ?? []).slice(0, PAGE_SIZE);

  const setCategory = (category?: string) =>
    void navigate({ search: (previous) => ({ ...previous, category, page: undefined }) });

  const setSort = (sort: string) =>
    void navigate({ search: (previous) => ({ ...previous, sort: sort || undefined, page: undefined }) });

  const handleBrandToggle = (brand: string) => {
    resetPage();
    setSelectedBrands((prev) =>
      prev.includes(brand) ? prev.filter((b) => b !== brand) : [...prev, brand],
    );
  };

  const handleClearAll = () => {
    setPage(1);
    setMaxPriceState(150000);
    setInStockOnly(false);
    setSelectedBrands([]);
    setMinRating(0);
    setMinDiscount(0);
    setCategory(undefined);
  };

  const currentCategoryTitle = search.q
    ? `Search Results for “${search.q}”`
    : search.category ?? "All Products";

  return (
    <div className="mx-auto max-w-7xl px-4 py-5 sm:px-6 lg:px-8">
      {/* Breadcrumbs */}
      <nav
        className="mb-4 flex items-center gap-1.5 text-xs text-muted-foreground"
        aria-label="Breadcrumb"
      >
        <Link to="/" className="flex items-center gap-1 hover:text-primary">
          <Home className="size-3.5" /> Home
        </Link>
        <ChevronRight className="size-3 text-muted-foreground/60" />
        <Link to="/products" search={{}} className="hover:text-primary">
          Catalog
        </Link>
        {search.category && (
          <>
            <ChevronRight className="size-3 text-muted-foreground/60" />
            <span className="font-bold text-foreground">{search.category}</span>
          </>
        )}
        {search.q && (
          <>
            <ChevronRight className="size-3 text-muted-foreground/60" />
            <span className="font-bold text-foreground">“{search.q}”</span>
          </>
        )}
      </nav>

      {/* Main Listing Header with Poorvika layout */}
      <div className="mb-6 flex flex-col gap-4 border-b border-border bg-card p-5 rounded-lg shadow-2xs sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-black text-foreground sm:text-3xl">
            {currentCategoryTitle}
          </h1>
          <p className="mt-1 text-xs font-bold text-muted-foreground">
            {query.isLoading
              ? "Loading products…"
              : `Showing ${(page - 1) * PAGE_SIZE + (filteredProducts.length ? 1 : 0)}–${(page - 1) * PAGE_SIZE + filteredProducts.length}${hasNextPage ? "+" : ""} products`}
          </p>
        </div>

        {/* Sorting Controls as Poorvika-style pills / tabs */}
        <div className="flex flex-wrap items-center gap-1.5">
          <Button
            variant="outline"
            size="sm"
            className="lg:hidden flex items-center gap-1.5 rounded-full"
            onClick={() => setMobileFilters(true)}
          >
            <SlidersHorizontal className="size-3.5" /> Filters
          </Button>

          <span className="hidden text-xs font-bold uppercase tracking-wider text-muted-foreground sm:inline-block mr-1">
            Sort By:
          </span>

          <div className="hidden sm:flex flex-wrap items-center gap-1 bg-muted/60 p-1 rounded-full border border-border">
            {sortOptions.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setSort(opt.value)}
                className={`rounded-full px-3 py-1 text-xs font-bold transition cursor-pointer ${
                  (search.sort ?? "") === opt.value
                    ? "bg-primary text-white shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Fallback mobile dropdown */}
          <select
            value={search.sort ?? ""}
            onChange={(event) => setSort(event.target.value)}
            aria-label="Sort products"
            className="h-8 rounded-full border border-input bg-card px-3 text-xs font-bold sm:hidden"
          >
            {sortOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Grid with Left Sidebar Filters */}
      <div className="grid gap-7 lg:grid-cols-[250px_1fr]">
        {/* Left Sidebar */}
        <div className="hidden lg:block">
          <div className="sticky top-28 rounded-lg border border-border bg-card p-5 shadow-2xs">
            <ProductFilters
              category={search.category}
              maxPrice={maxPrice}
              inStockOnly={inStockOnly}
              selectedBrands={selectedBrands}
              minRating={minRating}
              minDiscount={minDiscount}
              onCategoryChange={setCategory}
              onMaxPriceChange={setMaxPrice}
              onInStockChange={(value) => { resetPage(); setInStockOnly(value); }}
              onBrandToggle={handleBrandToggle}
              onRatingChange={(value) => { resetPage(); setMinRating(value); }}
              onDiscountChange={(value) => { resetPage(); setMinDiscount(value); }}
              onClearAll={handleClearAll}
            />
          </div>
        </div>

        {/* Main Product Grid */}
        <div>
          <ProductGrid
            products={filteredProducts}
            isLoading={query.isLoading}
            {...(query.error instanceof Error ? { error: query.error.message } : {})}
            onRetry={() => void query.refetch()}
          />
          {!query.error && (page > 1 || hasNextPage) && (
            <nav className="mt-6 flex items-center justify-center gap-4" aria-label="Product pages">
              <Button variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                Previous
              </Button>
              <span className="text-sm font-semibold">Page {page}</span>
              <Button variant="outline" disabled={!hasNextPage} onClick={() => setPage(page + 1)}>
                Next
              </Button>
            </nav>
          )}
        </div>
      </div>

      {/* Mobile Filters Drawer */}
      {mobileFilters && (
        <div
          className="fixed inset-0 z-50 bg-foreground/40 lg:hidden"
          onClick={() => setMobileFilters(false)}
        >
          <div
            className="ml-auto h-full w-[min(88vw,380px)] overflow-y-auto bg-card p-6 shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between border-b border-border pb-3">
              <h2 className="font-extrabold">Filter Products</h2>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => setMobileFilters(false)}
                aria-label="Close filters"
              >
                <X className="size-4" />
              </Button>
            </div>
            <ProductFilters
              category={search.category}
              maxPrice={maxPrice}
              inStockOnly={inStockOnly}
              selectedBrands={selectedBrands}
              minRating={minRating}
              minDiscount={minDiscount}
              onCategoryChange={setCategory}
              onMaxPriceChange={setMaxPrice}
              onInStockChange={(value) => { resetPage(); setInStockOnly(value); }}
              onBrandToggle={handleBrandToggle}
              onRatingChange={(value) => { resetPage(); setMinRating(value); }}
              onDiscountChange={(value) => { resetPage(); setMinDiscount(value); }}
              onClearAll={handleClearAll}
            />
            <Button
              className="mt-6 w-full"
              onClick={() => setMobileFilters(false)}
            >
              Apply Filters
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
