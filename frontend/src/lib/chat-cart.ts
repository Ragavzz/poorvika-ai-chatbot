import type { Product } from "@/services/api";

type CartItem = { product: Product; quantity: number };
type CartActions = {
  getItems: () => CartItem[];
  addToCart: (product: Product) => boolean;
  removeFromCart: (id: string | number) => void;
  updateQuantity: (id: string | number, quantity: number, verifiedProduct?: Product) => void;
};

/** Execute the server's cart instruction against the current client cart only. */
export async function applyChatCartResponse(
  response: string,
  cart: CartActions,
  getProduct: (id: string) => Promise<Product>,
): Promise<string> {
  const addMarker = response.match(/\[\[SHOPAI_ADD_TO_CART:([^\]]+)\]\]/);
  const actionMarker = response.match(/\[\[SHOPAI_CART_ACTION:(\{[^\n]*?\})\]\]/);
  const visible = response
    .replace(/\[\[SHOPAI_ADD_TO_CART:[^\]]+\]\]/g, "")
    .replace(/\[\[SHOPAI_CART_ACTION:\{[^\n]*?\}\]\]/g, "");
  if (!addMarker && !actionMarker) return visible;
  // Each response describes a single cart operation.
  if (addMarker && actionMarker) return "Couldn't update your cart. Please try again.";
  if (addMarker?.[1]) {
    try {
      const product = await getProduct(addMarker[1]);
      const existing = cart
        .getItems()
        .find((item) => String(item.product.id) === String(product.id));
      if (typeof product.stock === "number" && (existing?.quantity ?? 0) + 1 > product.stock)
        return `Only ${product.stock} of ${product.name} are available.`;
      if (!cart.addToCart(product)) return `${product.name} is currently out of stock.`;
      return visible;
    } catch {
      return "Couldn't add this to your cart. Please add it from its product page.";
    }
  }
  try {
    const command: unknown = JSON.parse(actionMarker![1]!);
    if (!command || typeof command !== "object") throw new Error("Invalid cart command");
    const {
      action,
      product_id: id,
      expected_quantity: expected,
      quantity: target,
    } = command as Record<string, unknown>;
    if (
      typeof id !== "string" ||
      !["remove", "increase", "decrease", "set_quantity"].includes(String(action)) ||
      !Number.isSafeInteger(expected) ||
      !Number.isSafeInteger(target)
    )
      throw new Error("Invalid cart command");
    const item = cart.getItems().find(({ product }) => String(product.id) === id);
    if (!item) return "That product isn't in your cart.";
    if (item.quantity !== expected)
      return "Your cart changed while I was checking. Please try again.";
    const quantity =
      action === "set_quantity"
        ? Number(target)
        : action === "remove"
          ? 0
          : Math.max(0, item.quantity + (action === "increase" ? 1 : -1));
    if (quantity < 0) throw new Error("Invalid quantity change");
    if (target !== quantity) throw new Error("Invalid quantity change");
    let verifiedProduct: Product | undefined;
    if (quantity > item.quantity) {
      const fresh = await getProduct(id);
      if (String(fresh.id) !== id) throw new Error("Wrong product returned");
      verifiedProduct = fresh;
      if (fresh.inStock === false) return `${fresh.name} is currently out of stock.`;
      if (typeof fresh.stock === "number" && quantity > fresh.stock)
        return `Only ${fresh.stock} of ${fresh.name} are available.`;
      const current = cart.getItems().find(({ product }) => String(product.id) === id);
      if (!current || current.quantity !== expected)
        return "Your cart changed while I was checking. Please try again.";
    }
    if (quantity === 0) cart.removeFromCart(id);
    else cart.updateQuantity(id, quantity, verifiedProduct);
    // Confirm the client-side operation, rather than trusting a claimed mutation.
    return quantity === 0
      ? `Removed **${item.product.name}** from your cart.`
      : `Updated **${item.product.name}** to ${quantity} in your cart.`;
  } catch {
    return "Couldn't update your cart. Please try again.";
  }
}
