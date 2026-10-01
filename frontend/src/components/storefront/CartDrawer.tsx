import { Link } from "@tanstack/react-router";
import { Minus, Plus, ShoppingBag, Trash2, ArrowRight, ShieldCheck } from "lucide-react";
import { useState } from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { useCart } from "@/context/CartContext";
import phoneFallback from "@/assets/category-phone.jpg";

const money = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

export function CartDrawer() {
  const {
    items,
    totalItems,
    subtotal,
    isOpen,
    closeCart,
    updateQuantity,
    removeFromCart,
    clearCart,
  } = useCart();

  const [checkingOut, setCheckingOut] = useState(false);
  const [orderComplete, setOrderComplete] = useState(false);

  const handleCheckout = () => {
    setCheckingOut(true);
    setTimeout(() => {
      setCheckingOut(false);
      setOrderComplete(true);
      clearCart();
    }, 1200);
  };

  const handleClose = (open: boolean) => {
    if (!open) {
      closeCart();
      // Reset checkout success state after drawer closes
      setTimeout(() => setOrderComplete(false), 300);
    }
  };

  return (
    <Sheet open={isOpen} onOpenChange={handleClose}>
      <SheetContent
        side="right"
        className="flex w-full flex-col p-0 sm:max-w-md"
        aria-describedby={undefined}
      >
        <SheetHeader className="border-b border-border px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShoppingBag className="size-5 text-primary" />
              <SheetTitle className="text-lg font-bold">Shopping Cart</SheetTitle>
              {totalItems > 0 && (
                <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-extrabold text-primary">
                  {totalItems}
                </span>
              )}
            </div>
          </div>
        </SheetHeader>

        {orderComplete ? (
          <div className="flex flex-1 flex-col items-center justify-center p-8 text-center">
            <div className="mb-4 grid size-16 place-items-center rounded-full bg-emerald-100 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400">
              <ShieldCheck className="size-8" />
            </div>
            <h3 className="text-xl font-extrabold">Order Placed Successfully!</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Thank you for shopping with ShopTech. Your items are being prepared for dispatch.
            </p>
            <Button
              className="mt-6"
              onClick={() => {
                setOrderComplete(false);
                closeCart();
              }}
            >
              Continue Shopping
            </Button>
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center p-8 text-center">
            <div className="mb-4 grid size-16 place-items-center rounded-full bg-muted text-muted-foreground">
              <ShoppingBag className="size-8 opacity-40" />
            </div>
            <h3 className="text-lg font-bold">Your cart is empty</h3>
            <p className="mt-1 max-w-xs text-sm text-muted-foreground">
              Explore our real PostgreSQL catalog for earphones, chargers, cables, and more.
            </p>
            <Button asChild className="mt-6" onClick={closeCart}>
              <Link to="/products" search={{}}>
                Browse Products <ArrowRight className="size-4" />
              </Link>
            </Button>
          </div>
        ) : (
          <>
            {/* Scrollable Items List */}
            <div className="flex-1 divide-y divide-border overflow-y-auto px-6">
              {items.map(({ product, quantity }) => {
                const imageSrc =
                  product.image || product.images?.[0] || phoneFallback;
                const lineTotal = product.price * quantity;

                return (
                  <div key={String(product.id)} className="flex gap-4 py-5">
                    <Link
                      to="/products/$productId"
                      params={{ productId: String(product.id) }}
                      onClick={closeCart}
                      className="size-20 shrink-0 overflow-hidden rounded-md border border-border bg-product-stage p-1"
                    >
                      <img
                        src={imageSrc}
                        alt={product.name}
                        className="size-full object-contain"
                      />
                    </Link>

                    <div className="flex flex-1 flex-col justify-between">
                      <div>
                        {product.brand && (
                          <p className="text-[10px] font-bold uppercase tracking-wider text-primary">
                            {product.brand}
                          </p>
                        )}
                        <Link
                          to="/products/$productId"
                          params={{ productId: String(product.id) }}
                          onClick={closeCart}
                          className="line-clamp-2 text-sm font-semibold hover:text-primary"
                        >
                          {product.name}
                        </Link>
                        <div className="mt-1 text-sm font-bold">
                          {money.format(product.price)}
                        </div>
                      </div>

                      <div className="mt-3 flex items-center justify-between">
                        <div className="flex items-center rounded-md border border-border">
                          <button
                            type="button"
                            onClick={() =>
                              updateQuantity(product.id, quantity - 1)
                            }
                            className="grid size-7 place-items-center text-muted-foreground transition hover:bg-muted hover:text-foreground"
                            aria-label="Decrease quantity"
                          >
                            <Minus className="size-3.5" />
                          </button>
                          <span className="w-8 text-center text-xs font-bold">
                            {quantity}
                          </span>
                          <button
                            type="button"
                            onClick={() =>
                              updateQuantity(product.id, quantity + 1)
                            }
                            className="grid size-7 place-items-center text-muted-foreground transition hover:bg-muted hover:text-foreground"
                            aria-label="Increase quantity"
                          >
                            <Plus className="size-3.5" />
                          </button>
                        </div>

                        <div className="flex items-center gap-3">
                          <span className="text-xs font-bold text-muted-foreground">
                            {money.format(lineTotal)}
                          </span>
                          <button
                            type="button"
                            onClick={() => removeFromCart(product.id)}
                            className="text-muted-foreground transition hover:text-destructive"
                            aria-label="Remove item"
                          >
                            <Trash2 className="size-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Cart Summary and Checkout */}
            <div className="border-t border-border bg-muted/20 p-6 space-y-4">
              <div className="space-y-1.5 text-sm">
                <div className="flex justify-between text-muted-foreground">
                  <span>Subtotal ({totalItems} item{totalItems > 1 ? "s" : ""})</span>
                  <span>{money.format(subtotal)}</span>
                </div>
                <div className="flex justify-between text-muted-foreground">
                  <span>Shipping</span>
                  <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                    FREE
                  </span>
                </div>
                <div className="flex justify-between border-t border-border pt-2 text-base font-extrabold text-foreground">
                  <span>Total</span>
                  <span>{money.format(subtotal)}</span>
                </div>
              </div>

              <Button
                className="w-full"
                size="lg"
                disabled={checkingOut}
                onClick={handleCheckout}
              >
                {checkingOut ? "Processing..." : `Checkout • ${money.format(subtotal)}`}
              </Button>

              <div className="flex items-center justify-center gap-1.5 text-[11px] text-muted-foreground">
                <ShieldCheck className="size-3.5 text-emerald-600" />
                <span>Bank-grade 256-bit secure checkout</span>
              </div>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
