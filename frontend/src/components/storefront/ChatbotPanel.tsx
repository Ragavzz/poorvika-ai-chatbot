import { MessageCircle, Sparkles, X } from "lucide-react";
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
import { formatShoppingResponse } from "@/lib/shopping-response";
import { applyChatCartResponse } from "@/lib/chat-cart";
import { useCart } from "@/context/CartContext";

type ChatMessage = { id: number; role: "user" | "assistant"; text: string };
const welcomeMessage = "Hi! What are you looking for today?";

const suggestionChips = [
  "Sony earphones under ₹1000",
  "Apple accessories",
  "Best power banks",
];

export function ChatbotPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { items, addToCart, removeFromCart, updateQuantity } = useCart();
  const latestCartItems = useRef(items);
  latestCartItems.current = items;
  const recentProductIds = useRef<string[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: 1, role: "assistant", text: welcomeMessage },
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
        cart: latestCartItems.current.map(({ product, quantity }) => ({
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
      const visibleResponse = await applyChatCartResponse(
        response.replace(/\[\[SHOPAI_PRODUCTS:[^\]]*\]\]/g, ""),
        { getItems: () => latestCartItems.current, addToCart, removeFromCart, updateQuantity },
        api.getProduct,
      );
      const reply = formatShoppingResponse(visibleResponse);
      // Keep the opening welcome once, even if a service echoes it back.
      if (reply !== welcomeMessage) {
        setMessages((current) => [
          ...current,
          { id: Date.now() + 1, role: "assistant", text: reply },
        ]);
      }
      setStatus("ready");
    } catch {
      setMessages((current) => [
        ...current,
        {
          id: Date.now() + 1,
          role: "assistant",
          text: "Sorry, we couldn't complete your request. Please try again.",
        },
      ]);
      setStatus("error");
    }
  };

  return (
    <section
      className={`${open ? "flex" : "hidden"} shopping-chat fixed bottom-[5.5rem] right-4 z-50 mb-3 h-[min(620px,78dvh,calc(100dvh-7rem))] w-[calc(100vw-2rem)] max-w-[410px] min-h-0 flex-col overflow-hidden rounded-xl border border-border bg-card shadow-2xl animate-in fade-in slide-in-from-bottom-5 duration-200 sm:bottom-[6.25rem] sm:right-7 sm:max-h-[calc(100dvh-8rem)]`}
      aria-label="Shopping assistant"
    >
          {/* Header with Poorvika Orange-Red Gradient */}
          <header className="flex shrink-0 items-center gap-3 bg-gradient-to-r from-primary via-orange-600 to-amber-600 px-4 py-3.5 text-white shadow-xs">
            <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-white/20 backdrop-blur-xs">
              <MessageCircle className="size-5 text-white" />
            </span>
            <div className="min-w-0 flex-1">
              <h2 className="text-sm font-black">Poorvika Shopping Assistant</h2>
              <p className="text-[11px] text-white/80">
                How can I help you shop today?
              </p>
            </div>
            <Button
              variant="ghost"
              size="icon-sm"
              className="ml-auto shrink-0 text-white hover:bg-white/15 hover:text-white"
              onClick={onClose}
              aria-label="Close assistant"
            >
              <X className="size-4" />
            </Button>
          </header>

          {/* Quick Suggestions Chips */}
          <div className="flex shrink-0 items-center gap-1.5 overflow-x-auto border-b border-border/70 bg-muted/40 px-3 py-2 scrollbar-none">
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

          <Conversation className="min-h-0 min-w-0">
            <ConversationContent
              className="min-w-0 gap-3.5 p-4"
              scrollClassName="min-h-0 min-w-0 overflow-y-auto overflow-x-hidden overscroll-contain"
            >
              {messages.map((message) => (
                <Message key={message.id} from={message.role} className="min-w-0 shrink-0">
                  <MessageContent
                    className={
                      message.role === "user"
                        ? "shopping-chat-bubble bg-primary text-white rounded-2xl rounded-br-xs font-medium text-xs shadow-xs"
                        : "shopping-chat-bubble bg-muted/70 text-foreground rounded-2xl rounded-bl-xs text-xs"
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
                    <Shimmer>Finding the right products…</Shimmer>
                  </MessageContent>
                </Message>
              )}
            </ConversationContent>
            <ConversationScrollButton />
          </Conversation>

          <div className="shrink-0 border-t border-border bg-card p-3">
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
  );
}
