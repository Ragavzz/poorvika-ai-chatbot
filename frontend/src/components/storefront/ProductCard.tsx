import { memo } from "react";
import { Link } from "@tanstack/react-router";
import { Heart, ShoppingCart, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Product } from "@/services/api";
import { useCartActions } from "@/context/CartContext";
import phoneFallback from "@/assets/category-phone.jpg";

const money = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

export const ProductCard = memo(function ProductCard({ product }: { product: Product }) {
  const { addToCart } = useCartActions();
  const isOutOfStock = product.inStock === false;

  const discount =
    product.discount ??
    (product.originalPrice && product.originalPrice > product.price
      ? Math.round((1 - product.price / product.originalPrice) * 100)
      : undefined);

  const specs = Array.isArray(product.specifications)
    ? product.specifications.slice(0, 2).map((item) => item.value)
    : Object.values(product.specifications ?? {}).slice(0, 2);

  return (
    <article className="group relative flex h-full flex-col rounded-lg border border-border/80 bg-card p-4 transition-all duration-200 hover:-translate-y-1 hover:border-primary/50 hover:shadow-lg">
      {/* Top Badges */}
      <div className="flex items-center justify-between">
        {discount && discount > 0 ? (
          <span className="rounded bg-offer px-2 py-0.5 text-[11px] font-black uppercase text-white shadow-2xs">
            {discount}% OFF
          </span>
        ) : (
          <span />
        )}
        <Button
          variant="ghost"
          size="icon-sm"
          className="size-8 rounded-full text-muted-foreground hover:bg-accent hover:text-primary"
          aria-label={`Save ${product.name} to wishlist`}
        >
          <Heart className="size-4" />
        </Button>
      </div>

      {/* Product Image Stage */}
      <Link
        to="/products/$productId"
        params={{ productId: String(product.id) }}
        className="block mt-2"
      >
        <div className="relative aspect-square w-full overflow-hidden rounded bg-white p-2">
          <img
            src={product.image || product.images?.[0] || phoneFallback}
            alt={product.name}
            loading="lazy"
            decoding="async"
            width={480}
            height={480}
            className="size-full object-contain transition duration-300 group-hover:scale-105"
          />
        </div>

        {/* Brand & Name */}
        <div className="mt-3">
          <p className="text-[11px] font-extrabold uppercase tracking-wider text-primary">
            {product.brand ?? product.category ?? "Electronics"}
          </p>
          <h3 className="mt-1 line-clamp-2 min-h-10 text-sm font-bold leading-snug text-foreground group-hover:text-primary transition-colors">
            {product.name}
          </h3>
        </div>
      </Link>

      {/* Highlights / Specs */}
      {specs.length > 0 && (
        <p className="mt-1.5 line-clamp-1 text-[11px] text-muted-foreground">
          {specs.join(" • ")}
        </p>
      )}

      {/* Bottom section pinned to bottom */}
      <div className="mt-auto pt-3">
        {/* Rating Pill (Poorvika style green rating badge) */}
        {product.rating ? (
          <div className="mb-2 flex items-center gap-1.5">
            <span className="inline-flex items-center gap-0.5 rounded bg-emerald-700 px-1.5 py-0.5 text-[11px] font-black text-white">
              {product.rating} <Star className="size-2.5 fill-white text-white" />
            </span>
            {product.reviewCount ? (
              <span className="text-[11px] font-medium text-muted-foreground">
                ({product.reviewCount} Ratings)
              </span>
            ) : null}
          </div>
        ) : (
          <div className="mb-2 h-4" />
        )}

        {/* Price Row */}
        <div className="flex flex-wrap items-baseline gap-2">
          <strong className="text-lg font-black text-foreground">
            {money.format(product.price)}
          </strong>
          {product.originalPrice && product.originalPrice > product.price ? (
            <span className="text-xs text-muted-foreground line-through">
              {money.format(product.originalPrice)}
            </span>
          ) : null}
        </div>

        {/* Stock Status Indicator */}
        <div className="mt-2 flex items-center justify-between text-xs">
          {isOutOfStock ? (
            <span className="text-[11px] font-bold text-destructive">
              ● Out of Stock
            </span>
          ) : (
            <span className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
              ● In Stock
            </span>
          )}
        </div>

        {/* Add to Cart Button */}
        <Button
          className="mt-3 w-full rounded font-bold shadow-xs cursor-pointer"
          disabled={isOutOfStock}
          variant={isOutOfStock ? "outline" : "default"}
          onClick={() => addToCart(product)}
        >
          <ShoppingCart className="size-4" />{" "}
          {isOutOfStock ? "Out of Stock" : "Add to Cart"}
        </Button>
      </div>
    </article>
  );
});
