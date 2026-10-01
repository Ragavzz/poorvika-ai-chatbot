import { PackageOpen, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ProductCard } from "./ProductCard";
import type { Product } from "@/services/api";

export function ProductGrid({
  products,
  isLoading,
  error,
  onRetry,
}: {
  products: Product[];
  isLoading?: boolean;
  error?: string;
  onRetry?: () => void;
}) {
  if (isLoading)
    return (
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, index) => (
          <div key={index} className="h-[430px] animate-pulse border border-border bg-muted" />
        ))}
      </div>
    );
  if (error)
    return (
      <div className="flex min-h-72 flex-col items-center justify-center border border-dashed border-border bg-muted/30 p-8 text-center">
        <PackageOpen className="mb-4 size-10 text-primary" />
        <h3 className="font-bold">Products are waiting for your backend</h3>
        <p className="mt-2 max-w-md text-sm text-muted-foreground">{error}</p>
        {onRetry && (
          <Button variant="outline" className="mt-5" onClick={onRetry}>
            <RefreshCw /> Try again
          </Button>
        )}
      </div>
    );
  if (!products.length)
    return (
      <div className="flex min-h-72 flex-col items-center justify-center border border-dashed border-border p-8 text-center">
        <PackageOpen className="mb-4 size-10 text-muted-foreground" />
        <h3 className="font-bold">No products found</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          Try broadening your search or removing a filter.
        </p>
      </div>
    );
  return (
    <div className="grid grid-cols-2 gap-3 sm:gap-5 lg:grid-cols-3 xl:grid-cols-4">
      {products.map((product) => (
        <ProductCard key={product.id} product={product} />
      ))}
    </div>
  );
}
