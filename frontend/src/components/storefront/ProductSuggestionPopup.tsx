import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useRouterState } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Sparkles, X } from "lucide-react";
import { beginSuggestionTiming, recordSuggestionTiming } from "@/lib/suggestion-timing";
import type { Product } from "@/services/api";
import { getProductSuggestionContext, getProductSuggestions } from "@/lib/product-suggestions";

export function ProductSuggestionPopup({
  open,
  onSelect,
}: {
  open: boolean;
  onSelect: (text: string, productId?: string) => void;
}) {
  const { pathname, search } = useRouterState({ select: (state) => state.location });
  const matches = useRouterState({ select: (state) => state.matches });
  const params = matches.find((match) => "productId" in match.params)?.params as
    { productId?: string } | undefined;
  // Observe the existing product cache without refetching product data.
  const product = useQuery<Product>({ queryKey: ["product", params?.productId], enabled: false });
  const context = /^\/products\/?$/.test(pathname)
    ? getProductSuggestionContext(search)
    : params?.productId && product.data && !product.isError
      ? getProductSuggestionContext({}, product.data)
      : null;
  const contextKey = context?.key;
  useLayoutEffect(() => {
    if (contextKey) beginSuggestionTiming(contextKey);
  }, [contextKey]);
  const generated = useQuery({
    queryKey: ["product-suggestions", context?.key],
    queryFn: () => getProductSuggestions(context!),
    enabled: !!context,
    staleTime: Infinity,
    gcTime: Infinity,
    retry: false,
    retryOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
  const dismissed = useRef(new Set<string>());
  const [, refresh] = useState(0);
  useEffect(() => {
    if (
      open ||
      !contextKey ||
      !generated.data ||
      generated.isError ||
      dismissed.current.has(contextKey)
    )
      return;
    let second = 0;
    const first = requestAnimationFrame(() => {
      second = requestAnimationFrame(() => recordSuggestionTiming(contextKey, "visible"));
    });
    return () => {
      cancelAnimationFrame(first);
      cancelAnimationFrame(second);
    };
  }, [open, contextKey, generated.data, generated.isError]);
  if (
    open ||
    !context ||
    !generated.data ||
    generated.isError ||
    dismissed.current.has(context.key)
  )
    return null;
  const dismiss = () => {
    dismissed.current.add(context.key);
    refresh((value) => value + 1);
  };
  return (
    <aside
      aria-label="Product suggestions"
      className="absolute bottom-full right-0 mb-3 max-h-[calc(100dvh-7rem)] w-[min(320px,calc(100vw-2rem))] overflow-y-auto rounded-xl border border-border bg-card p-3 text-foreground shadow-xl"
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
        {generated.data.map((text) => (
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
    </aside>
  );
}
