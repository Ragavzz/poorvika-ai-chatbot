import { useQuery } from "@tanstack/react-query";
import { Link, createFileRoute } from "@tanstack/react-router";
import { ChevronRight, PackageOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ProductDetails } from "@/components/storefront/ProductDetails";
import { api } from "@/services/api";

export const Route = createFileRoute("/products/$productId")({
  head: ({ params }) => ({
    meta: [
      { title: `Product ${params.productId} — Mobile Mart` },
      {
        name: "description",
        content: "View price, availability and specifications for this electronics product.",
      },
      { property: "og:title", content: "Product details — Mobile Mart" },
      {
        property: "og:description",
        content: "Review product pricing and specifications before you buy.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: ProductDetailsPage,
});
function ProductDetailsPage() {
  const { productId } = Route.useParams();
  const product = useQuery({
    queryKey: ["product", productId],
    queryFn: () => api.getProduct(productId),
    retry: false,
  });
  return (
    <div className="mx-auto max-w-7xl px-4 py-7 sm:px-6 lg:px-8">
      <nav className="mb-7 flex items-center gap-2 text-xs text-muted-foreground">
        <Link to="/">Home</Link>
        <ChevronRight className="size-3" />
        <Link to="/products" search={{}}>
          Products
        </Link>
        <ChevronRight className="size-3" />
        <span>Details</span>
      </nav>
      {product.isLoading ? (
        <div className="grid gap-10 lg:grid-cols-2">
          <div className="aspect-square animate-pulse bg-muted" />
          <div className="h-[500px] animate-pulse bg-muted" />
        </div>
      ) : product.data ? (
        <ProductDetails product={product.data} />
      ) : (
        <div className="grid min-h-96 place-items-center border border-dashed border-border text-center">
          <div>
            <PackageOpen className="mx-auto size-12 text-primary" />
            <h1 className="mt-4 text-2xl font-bold">Product unavailable</h1>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">
              {product.error instanceof Error
                ? product.error.message
                : "This product could not be loaded."}
            </p>
            <Button asChild className="mt-5">
              <Link to="/products" search={{}}>
                Back to products
              </Link>
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
