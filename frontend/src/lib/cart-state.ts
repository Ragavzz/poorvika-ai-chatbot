import type { Product } from "@/services/api";

export type StoredCartItem = { product: Product; quantity: number };
export const CART_STORAGE_KEY = "shopai_cart_items";

export function cartQuantityAllowed(product: Product, quantity: number): boolean {
  return (
    Number.isSafeInteger(quantity) &&
    quantity >= 0 &&
    (quantity === 0 || product.inStock !== false) &&
    (typeof product.stock !== "number" || quantity <= product.stock)
  );
}

export function setCartQuantity(
  items: StoredCartItem[],
  id: string | number,
  quantity: number,
  verifiedProduct?: Product,
): StoredCartItem[] {
  const item = items.find(({ product }) => String(product.id) === String(id));
  if (!item || !Number.isSafeInteger(quantity) || quantity < 0) return items;
  // Reductions remain available even if a product has since gone out of stock.
  const product =
    verifiedProduct && String(verifiedProduct.id) === String(id) ? verifiedProduct : item.product;
  if (quantity > item.quantity && !cartQuantityAllowed(product, quantity)) return items;
  return quantity === 0
    ? items.filter((item) => String(item.product.id) !== String(id))
    : items.map((item) => (String(item.product.id) === String(id) ? { product, quantity } : item));
}

export function cartTotals(items: StoredCartItem[]) {
  return {
    totalItems: items.reduce((sum, item) => sum + item.quantity, 0),
    subtotal: items.reduce((sum, item) => sum + item.product.price * item.quantity, 0),
  };
}

export function readCartItems(storage: Pick<Storage, "getItem">): StoredCartItem[] {
  const stored = storage.getItem(CART_STORAGE_KEY);
  return stored ? JSON.parse(stored) : [];
}

export function saveCartItems(storage: Pick<Storage, "setItem">, items: StoredCartItem[]) {
  storage.setItem(CART_STORAGE_KEY, JSON.stringify(items));
}
