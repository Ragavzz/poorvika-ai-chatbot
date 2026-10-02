import { lazy, Suspense, useState } from "react";
import { MessageCircle, X } from "lucide-react";
import { Button } from "@/components/ui/button";

const ChatbotPanel = lazy(() =>
  import("./ChatbotPanel").then((module) => ({ default: module.ChatbotPanel })),
);

export function Chatbot() {
  const [open, setOpen] = useState(false);
  const [hasOpened, setHasOpened] = useState(false);

  const toggle = () => {
    if (!hasOpened) setHasOpened(true);
    setOpen((value) => !value);
  };

  return (
    <div className="fixed bottom-5 right-4 z-50 sm:bottom-7 sm:right-7">
      {hasOpened && (
        <Suspense
          fallback={open ? (
            <div className="fixed bottom-[5.5rem] right-4 z-50 grid h-[min(620px,78vh)] w-[calc(100vw-2rem)] max-w-[410px] place-items-center rounded-xl border border-border bg-card text-sm text-muted-foreground shadow-2xl sm:bottom-[6.25rem] sm:right-7">
              Opening shopping assistant…
            </div>
          ) : null}
        >
          <ChatbotPanel open={open} onClose={() => setOpen(false)} />
        </Suspense>
      )}
      <Button
        onClick={toggle}
        size="lg"
        className="ml-auto h-13 rounded-full bg-gradient-to-r from-primary to-orange-600 px-5 text-white shadow-xl hover:from-primary/95 hover:to-orange-600/95 hover:shadow-2xl transition-all cursor-pointer flex items-center gap-2.5"
        aria-label={open ? "Close shopping assistant" : "Open shopping assistant"}
        aria-expanded={open}
      >
        {open ? <X className="size-5" /> : <MessageCircle className="size-5" />}
        <span className="font-extrabold text-sm tracking-wide">
          {open ? "Close" : "ShopAI Assistant"}
        </span>
      </Button>
    </div>
  );
}
