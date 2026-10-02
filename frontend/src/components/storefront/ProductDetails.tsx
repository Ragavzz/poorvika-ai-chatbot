import { useState } from "react";
import {
  AlertCircle,
  Check,
  Heart,
  Minus,
  Plus,
  ShieldCheck,
  ShoppingCart,
  Star,
  Truck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Product } from "@/services/api";
import { useCart } from "@/context/CartContext";
import phoneFallback from "@/assets/category-phone.jpg";

const money = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

export function ProductDetails({ product }: { product: Product }) {
  const { addToCart } = useCart();
  const [quantity, setQuantity] = useState(1);

  const images =
    product.images && product.images.length > 0
      ? product.images
      : product.image
        ? [product.image]
        : [phoneFallback];

  const [activeImage, setActiveImage] = useState<string>(images[0] || phoneFallback);

  const isOutOfStock = product.inStock === false;

  const discount =
    product.discount ??
    (product.originalPrice && product.originalPrice > product.price
      ? Math.round((1 - product.price / product.originalPrice) * 100)
      : undefined);

  const specs = Array.isArray(product.specifications)
    ? product.specifications
    : Object.entries(product.specifications ?? {}).map(([label, value]) => ({
        label,
        value,
      }));

  return (
    <div className="grid gap-10 lg:grid-cols-2">
      {/* Left: Product Images & Gallery */}
      <div className="sticky top-28 self-start space-y-4">
        <div className="relative aspect-square overflow-hidden rounded-lg border border-border bg-product-stage p-6 sm:p-12">
          {discount && discount > 0 ? (
            <span className="absolute left-4 top-4 z-10 rounded-sm bg-offer px-2.5 py-1 text-xs font-extrabold text-offer-foreground shadow-sm">
              {discount}% OFF
            </span>
          ) : null}
          <img
            src={activeImage}
            alt={product.name}
            width={900}
            height={900}
            className="mx-auto size-full object-contain"
          />
        </div>

        {images.length > 1 && (
          <div className="flex gap-3 overflow-x-auto pb-2">
            {images.map((img, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setActiveImage(img)}
                className={`size-20 shrink-0 overflow-hidden rounded-md border-2 bg-product-stage p-1 transition ${
                  activeImage === img
                    ? "border-primary shadow-sm"
                    : "border-border hover:border-muted-foreground/50"
                }`}
                aria-label={`View image ${idx + 1}`}
              >
                <img
                  src={img}
                  alt={`${product.name} view ${idx + 1}`}
                  loading="lazy"
                  decoding="async"
                  className="size-full object-contain"
                />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Right: Product Information & Actions */}
      <div className="py-2">
        <div className="flex items-center justify-between">
          <p className="text-xs font-extrabold uppercase tracking-wider text-primary">
            {product.brand ?? product.category ?? "Mobile Mart Catalog"}
          </p>
          {product.category && (
            <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-semibold text-muted-foreground">
              {product.category}
            </span>
          )}
        </div>

        <h1 className="mt-2 text-3xl font-black leading-tight sm:text-4xl">
          {product.name}
        </h1>

        {product.rating ? (
          <div className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
            <div className="flex items-center gap-1 rounded bg-amber-50 px-2 py-0.5 text-xs font-bold text-amber-800 dark:bg-amber-950 dark:text-amber-200">
              <Star className="size-3.5 fill-amber-500 text-amber-500" />
              {product.rating}
            </div>
            {product.reviewCount ? (
              <span>({product.reviewCount} customer reviews)</span>
            ) : null}
          </div>
        ) : null}

        <div className="mt-5 flex items-baseline gap-3">
          <strong className="text-3xl font-black">
            {money.format(product.price)}
          </strong>
          {product.originalPrice && product.originalPrice > product.price && (
            <span className="text-lg text-muted-foreground line-through">
              {money.format(product.originalPrice)}
            </span>
          )}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Inclusive of all taxes • Genuine product with manufacturer warranty
        </p>

        {product.description && (
          <p className="mt-6 leading-7 text-muted-foreground">
            {product.description}
          </p>
        )}

        {/* Availability Status */}
        <div className="mt-6 flex items-center gap-2">
          {isOutOfStock ? (
            <div className="flex items-center gap-1.5 text-sm font-bold text-destructive">
              <AlertCircle className="size-4" />
              <span>Currently Out of Stock</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-sm font-bold text-emerald-600 dark:text-emerald-400">
              <Check className="size-4" />
              <span>In Stock — Ready to ship</span>
            </div>
          )}
        </div>

        {/* Quantity and Add to Cart */}
        <div className="mt-6 flex flex-wrap items-center gap-4">
          {!isOutOfStock && (
            <div className="flex items-center rounded-md border border-border">
              <button
                type="button"
                onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                className="grid size-11 place-items-center text-muted-foreground transition hover:bg-muted hover:text-foreground"
                aria-label="Decrease quantity"
              >
                <Minus className="size-4" />
              </button>
              <span className="w-12 text-center text-base font-bold">
                {quantity}
              </span>
              <button
                type="button"
                onClick={() => setQuantity((q) => q + 1)}
                className="grid size-11 place-items-center text-muted-foreground transition hover:bg-muted hover:text-foreground"
                aria-label="Increase quantity"
              >
                <Plus className="size-4" />
              </button>
            </div>
          )}

          <Button
            size="lg"
            className="flex-1"
            disabled={isOutOfStock}
            onClick={() => addToCart(product, quantity)}
          >
            <ShoppingCart className="size-5" />{" "}
            {isOutOfStock ? "Out of stock" : "Add to cart"}
          </Button>

          <Button size="lg" variant="outline" aria-label="Add to wishlist">
            <Heart className="size-5" />
          </Button>
        </div>

        <div className="mt-8 grid grid-cols-2 gap-px border border-border bg-border">
          <div className="bg-background p-4">
            <Truck className="mb-2 size-5 text-primary" />
            <strong className="block text-sm">Fast delivery</strong>
            <span className="text-xs text-muted-foreground">
              Free shipping across India
            </span>
          </div>
          <div className="bg-background p-4">
            <ShieldCheck className="mb-2 size-5 text-primary" />
            <strong className="block text-sm">Secure purchase</strong>
            <span className="text-xs text-muted-foreground">
              Direct PostgreSQL verified catalog
            </span>
          </div>
        </div>

        {/* Key Specifications */}
        <section className="mt-9">
          <h2 className="border-b border-border pb-3 text-xl font-extrabold">
            Key specifications
          </h2>
          {specs.length ? (
            <dl className="divide-y divide-border">
              {specs.map((spec) => (
                <div
                  key={spec.label}
                  className="grid grid-cols-2 gap-5 py-3 text-sm"
                >
                  <dt className="text-muted-foreground">{spec.label}</dt>
                  <dd className="font-semibold text-foreground">
                    {String(spec.value)}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="py-5 text-sm text-muted-foreground">
              Detailed specifications will appear when supplied by the product API.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
