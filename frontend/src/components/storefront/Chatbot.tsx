import { Bot, MessageCircle, Sparkles, X } from "lucide-react";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import { Message, MessageContent, MessageResponse } from "@/components/ai-elements/message";
import {
  PromptInput,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
} from "@/components/ai-elements/prompt-input";
import { Shimmer } from "@/components/ai-elements/shimmer";
import { api } from "@/services/api";
import { useCart } from "@/context/CartContext";

type ChatMessage = { id: number; role: "user" | "assistant"; text: string };

const suggestionChips = [
  "Sony earphones under ₹1000",
  "Apple accessories",
  "Best power banks",
  "Mixer grinders",
];

export function Chatbot() {
  const { items, addToCart } = useCart();
  const recentProductIds = useRef<string[]>([]);
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 1,
      role: "assistant",
      text: "Namaste! I’m your Poorvika AI shopping assistant powered by our live PostgreSQL catalog. What are you looking to buy today?",
    },
  ]);
  const [status, setStatus] = useState<"ready" | "submitted" | "error">("ready");

  const send = async ({ text }: { text: string }) => {
    const clean = text.trim();
    if (!clean || status === "submitted") return;
    setMessages((current) => [...current, { id: Date.now(), role: "user", text: clean }]);
    setStatus("submitted");
    try {
      const clientContext = {
        recent_product_ids: recentProductIds.current,
        cart: items.map(({ product, quantity }) => ({
          id: product.id,
          name: product.name,
          price: product.price,
          quantity,
        })),
      };
      const response = await api.chat(
        `${clean}\n\n<shopai_client_context>${JSON.stringify(clientContext)}</shopai_client_context>`,
      );
      const productMarker = response.match(/\[\[SHOPAI_PRODUCTS:([^\]]*)\]\]/);
      if (productMarker) {
        recentProductIds.current = productMarker[1]?.split(",").filter(Boolean) ?? [];
      }
      const addMarker = response.match(/\[\[SHOPAI_ADD_TO_CART:([^\]]+)\]\]/);
      let visibleResponse = response.replace(/\[\[SHOPAI_PRODUCTS:[^\]]*\]\]/g, "");
      if (addMarker?.[1]) {
        try {
          const product = await api.getProduct(addMarker[1]);
          addToCart(product);
          visibleResponse = visibleResponse.replace(addMarker[0], "");
        } catch {
          visibleResponse = visibleResponse.replace(addMarker[0], "");
          visibleResponse += "\n\nI found the product, but couldn't update the cart. Please add it from its product page.";
        }
      }
      setMessages((current) => [
        ...current,
        { id: Date.now() + 1, role: "assistant", text: visibleResponse.trim() },
      ]);
      setStatus("ready");
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: Date.now() + 1,
          role: "assistant",
          text: error instanceof Error ? error.message : "The shopping assistant is unavailable.",
        },
      ]);
      setStatus("error");
    }
  };

  return (
    <div className="fixed bottom-5 right-4 z-50 sm:bottom-7 sm:right-7">
      {open && (
        <section
          className="mb-3 flex h-[min(620px,78vh)] w-[calc(100vw-2rem)] max-w-[410px] flex-col overflow-hidden rounded-xl border border-border bg-card shadow-2xl animate-in fade-in slide-in-from-bottom-5 duration-200"
          aria-label="Shopping assistant"
        >
          {/* Header with Poorvika Orange-Red Gradient */}
          <header className="flex items-center gap-3 bg-gradient-to-r from-primary via-orange-600 to-amber-600 px-4 py-3.5 text-white shadow-xs">
            <span className="grid size-9 place-items-center rounded-lg bg-white/20 backdrop-blur-xs">
              <Bot className="size-5 text-white" />
            </span>
            <div>
              <div className="flex items-center gap-1.5">
                <h2 className="text-sm font-black">Poorvika AI Assistant</h2>
                <span className="flex size-2 rounded-full bg-emerald-300 animate-pulse" />
              </div>
              <p className="text-[11px] text-white/80">
                Verified PostgreSQL Catalog • Grounded AI
              </p>
            </div>
            <Button
              variant="ghost"
              size="icon-sm"
              className="ml-auto text-white hover:bg-white/15 hover:text-white"
              onClick={() => setOpen(false)}
              aria-label="Close assistant"
            >
              <X className="size-4" />
            </Button>
          </header>

          {/* Quick Suggestions Chips */}
          <div className="flex items-center gap-1.5 overflow-x-auto border-b border-border/70 bg-muted/40 px-3 py-2 scrollbar-none">
            <Sparkles className="size-3 text-primary shrink-0 ml-1" />
            {suggestionChips.map((chip) => (
              <button
                key={chip}
                type="button"
                onClick={() => send({ text: chip })}
                className="shrink-0 rounded-full border border-border bg-card px-2.5 py-1 text-[11px] font-semibold text-foreground/80 transition hover:border-primary hover:text-primary cursor-pointer whitespace-nowrap"
              >
                {chip}
              </button>
            ))}
          </div>

          <Conversation>
            <ConversationContent className="gap-3.5 p-4">
              {messages.map((message) => (
                <Message key={message.id} from={message.role}>
                  <MessageContent
                    className={
                      message.role === "user"
                        ? "bg-primary text-white rounded-2xl rounded-br-xs font-medium text-xs shadow-xs"
                        : "bg-muted/70 text-foreground rounded-2xl rounded-bl-xs text-xs"
                    }
                  >
                    {message.role === "assistant" ? (
                      <MessageResponse>{message.text}</MessageResponse>
                    ) : (
                      message.text
                    )}
                  </MessageContent>
                </Message>
              ))}
              {status === "submitted" && (
                <Message from="assistant">
                  <MessageContent className="bg-muted/70 text-xs">
                    <Shimmer>Searching catalog and finding answers…</Shimmer>
                  </MessageContent>
                </Message>
              )}
            </ConversationContent>
            <ConversationScrollButton />
          </Conversation>

          <div className="border-t border-border bg-card p-3">
            <PromptInput onSubmit={send} className="bg-muted/30 border border-border rounded-lg">
              <PromptInputTextarea
                placeholder="Ask about earphones, chargers, appliances..."
                disabled={status === "submitted"}
                className="min-h-16 text-xs"
              />
              <PromptInputFooter className="justify-end pt-1">
                <PromptInputSubmit status={status} disabled={status === "submitted"} />
              </PromptInputFooter>
            </PromptInput>
          </div>
        </section>
      )}

      {/* Floating Trigger Button */}
      <Button
        onClick={() => setOpen((value) => !value)}
        size="lg"
        className="ml-auto h-13 rounded-full bg-gradient-to-r from-primary to-orange-600 px-5 text-white shadow-xl hover:from-primary/95 hover:to-orange-600/95 hover:shadow-2xl transition-all cursor-pointer flex items-center gap-2.5"
        aria-label={open ? "Close shopping assistant" : "Open shopping assistant"}
      >
        {open ? <X className="size-5" /> : <MessageCircle className="size-5" />}
        <span className="font-extrabold text-sm tracking-wide">
          {open ? "Close" : "ShopAI Assistant"}
        </span>
      </Button>
    </div>
  );
}
