import type { Product } from "@/services/api";

type CartItem = { product: Product; quantity: number };
type CartActions = {
  getItems: () => CartItem[];
  addToCart: (product: Product) => boolean;
  removeFromCart: (id: string | number) => void;
  updateQuantity: (id: string | number, quantity: number) => void;
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
      if (!cart.addToCart(product)) return `${product.name} is currently out of stock.`;
      return visible;
    } catch {
      return "Couldn't add this to your cart. Please add it from its product page.";
    }
  }
  try {
    const command: unknown = JSON.parse(actionMarker![1]!);
    if (!command || typeof command !== "object") throw new Error("Invalid cart command");
    const { action, product_id: id, expected_quantity: expected, quantity: target } = command as Record<string, unknown>;
    if (
      typeof id !== "string" ||
      !["remove", "increase", "decrease"].includes(String(action)) ||
      !Number.isSafeInteger(expected) || !Number.isSafeInteger(target)
    ) throw new Error("Invalid cart command");
    const item = cart.getItems().find(({ product }) => String(product.id) === id);
    if (!item) return "That product isn't in your cart.";
    if (item.quantity !== expected) return "Your cart changed while I was checking. Please try again.";
    const quantity = action === "remove" ? 0 : Math.max(0, item.quantity + (action === "increase" ? 1 : -1));
    if (target !== quantity) throw new Error("Invalid quantity change");
    if (action === "increase" && item.product.inStock === false) return `${item.product.name} is currently out of stock.`;
    if (quantity === 0) cart.removeFromCart(id);
    else cart.updateQuantity(id, quantity);
    // Confirm the client-side operation, rather than trusting a claimed mutation.
    return quantity === 0
      ? `Removed **${item.product.name}** from your cart.`
      : `Updated **${item.product.name}** to ${quantity} in your cart.`;
  } catch {
    return "Couldn't update your cart. Please try again.";
  }
}
