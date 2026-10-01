import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { ChevronRight, Home, SlidersHorizontal, X } from "lucide-react";
import { useState, useMemo } from "react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { ProductFilters } from "@/components/storefront/ProductFilters";
import { ProductGrid } from "@/components/storefront/ProductGrid";
import { api } from "@/services/api";

const searchSchema = z.object({
  q: z.string().optional(),
  category: z.string().optional(),
  sort: z.string().optional(),
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

function ProductsPage() {
  const search = Route.useSearch();
  const navigate = useNavigate({ from: "/products/" });

  // Filter states
  const [maxPrice, setMaxPrice] = useState(150000);
  const [inStockOnly, setInStockOnly] = useState(false);
  const [selectedBrands, setSelectedBrands] = useState<string[]>([]);
  const [minRating, setMinRating] = useState(0);
  const [minDiscount, setMinDiscount] = useState(0);
  const [mobileFilters, setMobileFilters] = useState(false);

  const requestQuery = {
    maxPrice,
    ...(selectedBrands.length > 0 ? { brand: selectedBrands } : {}),
    ...(search.category ? { category: search.category } : {}),
    ...(search.sort ? { sort: search.sort } : {}),
  };

  const query = useQuery({
    queryKey: [
      "products",
      search.q,
      search.category,
      search.sort,
      maxPrice,
      selectedBrands,
    ],
    queryFn: () =>
      search.q
        ? api.searchProducts({ ...requestQuery, query: search.q })
        : api.getProducts(requestQuery),
    retry: false,
  });

  // Client-side filtering refinement for inStock, minRating, minDiscount
  const filteredProducts = useMemo(() => {
    let items = query.data ?? [];

    if (inStockOnly) {
      items = items.filter((p) => p.inStock !== false);
    }
    if (minRating > 0) {
      items = items.filter((p) => (p.rating ?? 0) >= minRating);
    }
    if (minDiscount > 0) {
      items = items.filter((p) => {
        const disc =
          p.discount ??
          (p.originalPrice && p.originalPrice > p.price
            ? Math.round((1 - p.price / p.originalPrice) * 100)
            : 0);
        return disc >= minDiscount;
      });
    }

    return items;
  }, [query.data, inStockOnly, minRating, minDiscount]);

  const setCategory = (category?: string) =>
    void navigate({ search: (previous) => ({ ...previous, category }) });

  const setSort = (sort: string) =>
    void navigate({ search: (previous) => ({ ...previous, sort: sort || undefined }) });

  const handleBrandToggle = (brand: string) => {
    setSelectedBrands((prev) =>
      prev.includes(brand) ? prev.filter((b) => b !== brand) : [...prev, brand],
    );
  };

  const handleClearAll = () => {
    setMaxPrice(150000);
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
              : `Found ${filteredProducts.length} product${filteredProducts.length === 1 ? "" : "s"}`}
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
              onInStockChange={setInStockOnly}
              onBrandToggle={handleBrandToggle}
              onRatingChange={setMinRating}
              onDiscountChange={setMinDiscount}
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
              onInStockChange={setInStockOnly}
              onBrandToggle={handleBrandToggle}
              onRatingChange={setMinRating}
              onDiscountChange={setMinDiscount}
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
