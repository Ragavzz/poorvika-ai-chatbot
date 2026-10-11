import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { toast } from "sonner";
import type { Product } from "@/services/api";
import {
  CART_STORAGE_KEY,
  cartQuantityAllowed,
  cartTotals,
  readCartItems,
  saveCartItems,
  setCartQuantity,
} from "@/lib/cart-state";

export interface CartItem {
  product: Product;
  quantity: number;
}

interface CartState {
  items: CartItem[];
  totalItems: number;
  subtotal: number;
  isOpen: boolean;
}

interface CartActions {
  addToCart: (product: Product, quantity?: number) => boolean;
  removeFromCart: (productId: string | number) => void;
  updateQuantity: (productId: string | number, quantity: number, verifiedProduct?: Product) => void;
  clearCart: () => void;
  openCart: () => void;
  closeCart: () => void;
  toggleCart: () => void;
}

const CartStateContext = createContext<CartState | undefined>(undefined);
const CartActionsContext = createContext<CartActions | undefined>(undefined);

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<CartItem[]>(() => {
    if (typeof window === "undefined") return [];
    try {
      return readCartItems(localStorage);
    } catch {
      return [];
    }
  });

  const [isOpen, setIsOpen] = useState(false);
  const currentItems = useRef(items);
  currentItems.current = items;

  // Sync to localStorage whenever items change
  useEffect(() => {
    try {
      saveCartItems(localStorage, items);
    } catch (e) {
      console.error("Failed to save cart to localStorage", e);
    }
  }, [items]);

  // Keep this tab's shared cart state current when another tab changes the cart.
  useEffect(() => {
    const syncFromStorage = (event: StorageEvent) => {
      if (event.storageArea !== window.localStorage) return;
      if (event.key !== CART_STORAGE_KEY && event.key !== null) return;
      try {
        const storedItems: unknown = event.newValue ? JSON.parse(event.newValue) : [];
        if (Array.isArray(storedItems)) setItems(storedItems as CartItem[]);
      } catch {
        // Ignore malformed external storage values and preserve the current cart.
      }
    };

    window.addEventListener("storage", syncFromStorage);
    return () => window.removeEventListener("storage", syncFromStorage);
  }, []);

  const { totalItems, subtotal } = cartTotals(items);

  const addToCart = useCallback((product: Product, quantity: number = 1): boolean => {
    // Prevent adding out-of-stock products
    if (product.inStock === false) {
      toast.error(`${product.name} is currently out of stock.`);
      return false;
    }
    const existingQuantity =
      currentItems.current.find((item) => String(item.product.id) === String(product.id))
        ?.quantity ?? 0;
    if (
      !Number.isSafeInteger(quantity) ||
      quantity <= 0 ||
      !cartQuantityAllowed(product, existingQuantity + quantity)
    ) {
      toast.error(`Can't add this quantity; available stock is ${product.stock ?? "unknown"}.`);
      return false;
    }

    setItems((prevItems) => {
      const existingIndex = prevItems.findIndex(
        (item) => String(item.product.id) === String(product.id),
      );

      if (existingIndex > -1) {
        const updated = [...prevItems];
        const item = updated[existingIndex];
        if (item) {
          updated[existingIndex] = {
            product,
            quantity: item.quantity + quantity,
          };
          if (!cartQuantityAllowed(product, item.quantity + quantity)) return prevItems;
          currentItems.current = updated;
          return updated;
        }
      }

      const updated = [...prevItems, { product, quantity }];
      currentItems.current = updated;
      return updated;
    });

    toast.success(`Added to cart`, {
      description: `${product.name} (${quantity} item${quantity > 1 ? "s" : ""})`,
    });
    return true;
  }, []);

  const removeFromCart = useCallback((productId: string | number) => {
    setItems((prev) => prev.filter((item) => String(item.product.id) !== String(productId)));
    toast.info("Item removed from cart");
  }, []);

  const updateQuantity = useCallback(
    (productId: string | number, quantity: number, verifiedProduct?: Product) => {
      if (quantity <= 0) {
        removeFromCart(productId);
        return;
      }

      const item = currentItems.current.find(
        (item) => String(item.product.id) === String(productId),
      );
      const product =
        verifiedProduct && String(verifiedProduct.id) === String(productId)
          ? verifiedProduct
          : item?.product;
      if (item && product && quantity > item.quantity && !cartQuantityAllowed(product, quantity)) {
        toast.error(
          `Can't increase this quantity; available stock is ${item.product.stock ?? "unknown"}.`,
        );
        return;
      }
      setItems((prev) => {
        const updated = setCartQuantity(prev, productId, quantity, verifiedProduct);
        currentItems.current = updated;
        return updated;
      });
    },
    [removeFromCart],
  );

  const clearCart = useCallback(() => {
    setItems([]);
  }, []);

  const openCart = useCallback(() => setIsOpen(true), []);
  const closeCart = useCallback(() => setIsOpen(false), []);
  const toggleCart = useCallback(() => setIsOpen((prev) => !prev), []);

  const actions = useMemo(
    () => ({
      addToCart,
      removeFromCart,
      updateQuantity,
      clearCart,
      openCart,
      closeCart,
      toggleCart,
    }),
    [addToCart, removeFromCart, updateQuantity, clearCart, openCart, closeCart, toggleCart],
  );
  const state = useMemo(
    () => ({ items, totalItems, subtotal, isOpen }),
    [items, totalItems, subtotal, isOpen],
  );

  return (
    <CartActionsContext.Provider value={actions}>
      <CartStateContext.Provider value={state}>{children}</CartStateContext.Provider>
    </CartActionsContext.Provider>
  );
}

export function useCart() {
  const state = useContext(CartStateContext);
  const actions = useContext(CartActionsContext);
  if (!state || !actions) {
    throw new Error("useCart must be used within a CartProvider");
  }
  return { ...state, ...actions };
}

export function useCartActions() {
  const context = useContext(CartActionsContext);
  if (!context) {
    throw new Error("useCartActions must be used within a CartProvider");
  }
  return context;
}
