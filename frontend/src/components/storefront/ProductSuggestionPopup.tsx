import { createContext, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useRouterState } from "@tanstack/react-router";
import { skipToken, useQuery, useQueryClient } from "@tanstack/react-query";
import { Sparkles, X } from "lucide-react";
import { beginSuggestionTiming, recordSuggestionTiming } from "@/lib/suggestion-timing";
import { api, type Product } from "@/services/api";
import { getProductSuggestionContext, getProductSuggestions, getSuggestionQueryKey } from "@/lib/product-suggestions";

type ListingContextValue = {
  listing: { products: Product[]; filters: Record<string, unknown> } | null;
  setListing: (value: ListingContextValue["listing"]) => void;
};
export const ListingSuggestionContext = createContext<ListingContextValue | null>(null);
export function ListingSuggestionProvider({ children }: { children: React.ReactNode }) {
  const [listing, setListing] = useState<ListingContextValue["listing"]>(null);
  const value = useMemo(() => ({ listing, setListing }), [listing]);
  return <ListingSuggestionContext.Provider value={value}>{children}</ListingSuggestionContext.Provider>;
}

export function ProductSuggestionPopup({
  open,
  onSelect,
}: {
  open: boolean;
  onSelect: (text: string, productId?: string) => void;
}) {
  const { pathname, search } = useRouterState({ select: (state) => state.location });
  const queryClient = useQueryClient();
  const matches = useRouterState({ select: (state) => state.matches });
  const params = matches.find((match) => "productId" in match.params)?.params as
    { productId?: string } | undefined;
  // Observe the existing product cache without refetching product data.
  const product = useQuery<Product>({
    queryKey: ["product", params?.productId],
    queryFn: skipToken,
  });
  const listing = useContext(ListingSuggestionContext)?.listing;
  const context = /^\/products\/?$/.test(pathname)
    ? listing
      ? getProductSuggestionContext({ ...search, products: listing.products, filters: listing.filters })
      : null
    : params?.productId &&
        product.data &&
        !product.isError &&
        String(product.data.id) === params.productId
      ? getProductSuggestionContext({}, product.data)
      : null;
  const contextKey = context?.key;
  const timingContext = useRef<string | undefined>(undefined);
  if (contextKey !== timingContext.current) {
    timingContext.current = contextKey;
    if (contextKey) beginSuggestionTiming(contextKey, true);
  }
  const capabilities = useQuery({
    queryKey: ["chat-capabilities"],
    queryFn: ({ signal }) => api.getChatCapabilities(signal),
    staleTime: 30000,
    retry: false,
  });
  const modelConfiguration = capabilities.data?.model_configuration;
  const previousModelConfiguration = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (!modelConfiguration) return;
    if (previousModelConfiguration.current && previousModelConfiguration.current !== modelConfiguration) {
      void queryClient.invalidateQueries({ queryKey: ["model-product-suggestions-v3"] });
    }
    previousModelConfiguration.current = modelConfiguration;
  }, [modelConfiguration, queryClient]);
  const dismissed = useRef(new Set<string>());
  const generated = useQuery({
    queryKey: context ? getSuggestionQueryKey(context) : ["model-product-suggestions-v3", null],
    queryFn: ({ signal }) => getProductSuggestions(context!, signal, capabilities.data?.timeout_ms),
    enabled:
      !!context &&
      !open &&
      !dismissed.current.has(context.key),
    staleTime: 300000,
    retry: false,
  });
  useEffect(() => {
    if (!contextKey) return;
    if (capabilities.isError || generated.isError) {
      console.warn(
        "ShopAI suggestions unavailable",
        contextKey,
        capabilities.error || generated.error,
      );
    } else if (capabilities.data?.ollama_enabled === false) {
      console.info("ShopAI suggestions disabled by configuration", contextKey);
    }
  }, [
    contextKey,
    capabilities.isError,
    capabilities.error,
    capabilities.data?.ollama_enabled,
    generated.isError,
    generated.error,
  ]);
  const [readyKey, setReadyKey] = useState<string | null>(null);
  useEffect(() => {
    setReadyKey(null);
    if (!contextKey) return;
    if (open) {
      dismissed.current.add(contextKey);
      return;
    }
    if (dismissed.current.has(contextKey)) return;
    beginSuggestionTiming(contextKey);
    recordSuggestionTiming(contextKey, "context_available");
    setReadyKey(contextKey);
  }, [contextKey, open]);
  useEffect(() => {
    if (!contextKey) return;
    if (generated.isFetching) recordSuggestionTiming(contextKey, "loading");
    else if (capabilities.data?.ollama_enabled === false)
      recordSuggestionTiming(contextKey, "disabled");
    else if (capabilities.isError || generated.isError)
      recordSuggestionTiming(contextKey, "failure", {
        reason: String(capabilities.error || generated.error),
      });
  }, [
    contextKey,
    generated.isFetching,
    generated.isError,
    generated.error,
    capabilities.isError,
    capabilities.error,
    capabilities.data?.ollama_enabled,
  ]);
  const visible =
    !open &&
    !!contextKey &&
    readyKey === contextKey &&
    !dismissed.current.has(contextKey) &&
    capabilities.data?.ollama_enabled !== false &&
    !!generated.data &&
    !generated.isError;
  const showLoading = !!context && !open && !dismissed.current.has(context.key) &&
    readyKey === context.key && capabilities.data?.ollama_enabled !== false &&
    (capabilities.isLoading || generated.isFetching);
  const retry = () => {
    if (context) void generated.refetch();
  };
  useLayoutEffect(() => {
    if (!visible || !contextKey) return;
    let second = 0;
    const first = requestAnimationFrame(() => {
      second = requestAnimationFrame(() => recordSuggestionTiming(contextKey, "visible"));
    });
    return () => {
      cancelAnimationFrame(first);
      cancelAnimationFrame(second);
    };
  }, [visible, contextKey]);
  if (
    (!visible && !showLoading && !(context && generated.isError && readyKey === context.key)) ||
    !context ||
    capabilities.data?.ollama_enabled === false ||
    typeof document === "undefined"
  )
    return null;
  const dismiss = () => {
    dismissed.current.add(context.key);
    setReadyKey(null);
  };
  return createPortal(
    <aside
      aria-label="Product suggestions"
      className="fixed bottom-[5.5rem] right-4 z-50 max-h-[calc(100dvh-7rem)] w-[min(320px,calc(100vw-2rem))] overflow-y-auto rounded-xl border border-border bg-card p-3 text-foreground shadow-xl sm:bottom-[6.25rem] sm:right-7"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.stopPropagation();
          dismiss();
        }
      }}
    >
      <div className="mb-2 flex items-start gap-2">
        <Sparkles className="mt-0.5 size-4 shrink-0 text-primary" />
        <h2 className="min-w-0 flex-1 break-words text-sm font-bold">{context.title}</h2>
        <button
          type="button"
          onClick={dismiss}
          aria-label="Dismiss product suggestions"
          className="grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground hover:bg-muted focus-visible:outline-2 focus-visible:outline-primary"
        >
          <X className="size-4" />
        </button>
      </div>
      <div className="grid gap-1.5">
        {showLoading ? <p role="status" className="px-2 py-2 text-xs text-muted-foreground">Generating questions…</p> : null}
        {generated.isError ? (
          <div className="px-2 py-2 text-xs text-muted-foreground">
            <p>Suggestions could not be generated.</p>
            <button type="button" onClick={retry} disabled={generated.isFetching} className="mt-2 font-semibold text-primary underline disabled:opacity-60">
              {generated.isFetching ? "Retrying…" : "Try again"}
            </button>
          </div>
        ) : null}
        {(generated.isError ? [] : generated.data ?? []).map((text) => (
          <button
            key={text}
            type="button"
            onClick={() => {
              dismiss();
              onSelect(text, params?.productId);
            }}
            className="rounded-lg border border-border bg-background px-3 py-2 text-left text-xs font-medium break-words transition hover:border-primary hover:text-primary focus-visible:outline-2 focus-visible:outline-primary"
          >
            {text}
          </button>
        ))}
      </div>
    </aside>,
    document.body,
  );
}
