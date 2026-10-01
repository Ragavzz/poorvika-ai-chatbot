import { Checkbox } from "@/components/ui/checkbox";
import { Slider } from "@/components/ui/slider";
import { Star, RotateCcw } from "lucide-react";
import { categories } from "./CategoryNav";

export const popularBrands = [
  "Apple",
  "Sony",
  "Philips",
  "Samsung",
  "SanDisk",
  "V-Guard",
  "Mi",
  "Premier",
  "Crompton",
  "Symphony",
  "Inbase",
  "Bosch",
];

interface ProductFiltersProps {
  category?: string | undefined;
  maxPrice: number;
  inStockOnly: boolean;
  selectedBrands: string[];
  minRating: number;
  minDiscount: number;
  onCategoryChange: (value?: string | undefined) => void;
  onMaxPriceChange: (value: number) => void;
  onInStockChange: (value: boolean) => void;
  onBrandToggle: (brand: string) => void;
  onRatingChange: (rating: number) => void;
  onDiscountChange: (discount: number) => void;
  onClearAll: () => void;
}

export function ProductFilters({
  category,
  maxPrice,
  inStockOnly,
  selectedBrands,
  minRating,
  minDiscount,
  onCategoryChange,
  onMaxPriceChange,
  onInStockChange,
  onBrandToggle,
  onRatingChange,
  onDiscountChange,
  onClearAll,
}: ProductFiltersProps) {
  return (
    <aside className="space-y-6 text-sm" aria-label="Product filters">
      {/* Header with Clear All */}
      <div className="flex items-center justify-between border-b border-border pb-3.5">
        <h2 className="text-base font-black uppercase tracking-wide text-foreground">
          Filters
        </h2>
        <button
          type="button"
          onClick={onClearAll}
          className="flex items-center gap-1 text-xs font-bold text-primary hover:underline cursor-pointer"
        >
          <RotateCcw className="size-3" /> Clear All
        </button>
      </div>

      {/* Availability / Stock Status */}
      <div className="border-b border-border pb-5">
        <h3 className="mb-3 text-xs font-extrabold uppercase tracking-wider text-muted-foreground">
          Availability
        </h3>
        <label className="flex cursor-pointer items-center gap-2.5 font-medium text-foreground hover:text-primary">
          <Checkbox
            checked={inStockOnly}
            onCheckedChange={(checked) => onInStockChange(Boolean(checked))}
          />
          <span>In Stock Only</span>
        </label>
      </div>

      {/* Categories */}
      <div className="border-b border-border pb-5">
        <h3 className="mb-3 text-xs font-extrabold uppercase tracking-wider text-muted-foreground">
          Categories
        </h3>
        <div className="space-y-2.5">
          <label className="flex cursor-pointer items-center gap-2.5 font-medium text-foreground hover:text-primary">
            <Checkbox
              checked={!category}
              onCheckedChange={() => onCategoryChange(undefined)}
            />
            <span>All Categories</span>
          </label>
          {categories.map((item) => (
            <label
              key={item}
              className="flex cursor-pointer items-center gap-2.5 font-medium text-foreground hover:text-primary"
            >
              <Checkbox
                checked={category === item}
                onCheckedChange={(checked) => onCategoryChange(checked ? item : undefined)}
              />
              <span>{item}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Price Range */}
      <div className="border-b border-border pb-5">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-xs font-extrabold uppercase tracking-wider text-muted-foreground">
            Price Range
          </h3>
          <span className="text-xs font-black text-primary">
            Up to ₹{maxPrice.toLocaleString("en-IN")}
          </span>
        </div>
        <Slider
          min={100}
          max={150000}
          step={500}
          value={[maxPrice]}
          onValueChange={(value) => onMaxPriceChange(value[0] ?? 150000)}
        />
        <div className="mt-3 flex flex-wrap gap-1.5">
          {[1000, 3000, 10000, 50000].map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => onMaxPriceChange(p)}
              className={`rounded-full px-2 py-0.5 text-[11px] font-bold transition cursor-pointer ${
                maxPrice === p
                  ? "bg-primary text-white"
                  : "bg-muted text-muted-foreground hover:bg-border"
              }`}
            >
              ≤ ₹{p.toLocaleString("en-IN")}
            </button>
          ))}
        </div>
      </div>

      {/* Brands */}
      <div className="border-b border-border pb-5">
        <h3 className="mb-3 text-xs font-extrabold uppercase tracking-wider text-muted-foreground">
          Brands
        </h3>
        <div className="max-h-48 space-y-2.5 overflow-y-auto pr-1">
          {popularBrands.map((brand) => (
            <label
              key={brand}
              className="flex cursor-pointer items-center gap-2.5 font-medium text-foreground hover:text-primary"
            >
              <Checkbox
                checked={selectedBrands.includes(brand)}
                onCheckedChange={() => onBrandToggle(brand)}
              />
              <span>{brand}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Customer Rating */}
      <div className="border-b border-border pb-5">
        <h3 className="mb-3 text-xs font-extrabold uppercase tracking-wider text-muted-foreground">
          Customer Rating
        </h3>
        <div className="space-y-2">
          {[4, 3].map((stars) => (
            <label
              key={stars}
              className="flex cursor-pointer items-center gap-2.5 font-medium text-foreground hover:text-primary"
            >
              <Checkbox
                checked={minRating === stars}
                onCheckedChange={(checked) => onRatingChange(checked ? stars : 0)}
              />
              <div className="flex items-center gap-1">
                <span className="flex items-center gap-0.5 rounded bg-emerald-600 px-1.5 py-0.5 text-[10px] font-black text-white">
                  {stars}★
                </span>
                <span className="text-xs">& above</span>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Discount */}
      <div>
        <h3 className="mb-3 text-xs font-extrabold uppercase tracking-wider text-muted-foreground">
          Special Offers & Discount
        </h3>
        <div className="space-y-2">
          {[30, 20, 10].map((disc) => (
            <label
              key={disc}
              className="flex cursor-pointer items-center gap-2.5 font-medium text-foreground hover:text-primary"
            >
              <Checkbox
                checked={minDiscount === disc}
                onCheckedChange={(checked) => onDiscountChange(checked ? disc : 0)}
              />
              <span className="text-xs">{disc}% or more</span>
            </label>
          ))}
        </div>
      </div>
    </aside>
  );
}
