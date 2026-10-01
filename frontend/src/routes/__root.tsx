import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import { useEffect, type ReactNode } from "react";
import appCss from "../styles.css?url";
import { reportLovableError } from "../lib/lovable-error-reporting";
import { Navbar } from "@/components/storefront/Navbar";
import { Chatbot } from "@/components/storefront/Chatbot";
import { SiteFooter } from "@/components/storefront/SiteFooter";
import { Button } from "@/components/ui/button";
import { CartProvider } from "@/context/CartContext";
import { CartDrawer } from "@/components/storefront/CartDrawer";
import { Toaster } from "@/components/ui/sonner";

function NotFoundComponent() {
  return (
    <div className="grid min-h-[60vh] place-items-center px-4">
      <div className="text-center">
        <p className="text-7xl font-black text-primary">404</p>
        <h1 className="mt-3 text-2xl font-bold">We couldn’t find that page</h1>
        <p className="mt-2 text-muted-foreground">The product or page may have moved.</p>
        <Button asChild className="mt-6">
          <Link to="/">Return home</Link>
        </Button>
      </div>
    </div>
  );
}
function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();
  useEffect(() => {
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);
  return (
    <div className="grid min-h-[60vh] place-items-center px-4">
      <div className="text-center">
        <h1 className="text-2xl font-bold">This page didn’t load</h1>
        <p className="mt-2 text-muted-foreground">Please try again.</p>
        <Button
          className="mt-6"
          onClick={() => {
            router.invalidate();
            reset();
          }}
        >
          Try again
        </Button>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "Poorvika - Mobile, Electronics & Appliances" },
    ],
    links: [
      { rel: "stylesheet", href: appCss },
      { rel: "icon", href: "/favicon.png", type: "image/png" },
      { rel: "apple-touch-icon", href: "/favicon.png" },
      { rel: "preconnect", href: "https://fonts.googleapis.com" },
      { rel: "preconnect", href: "https://fonts.gstatic.com", crossOrigin: "anonymous" },
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap",
      },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});
function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}
function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  return (
    <QueryClientProvider client={queryClient}>
      <CartProvider>
        <Navbar />
        <main>
          <Outlet />
        </main>
        <SiteFooter />
        <Chatbot />
        <CartDrawer />
        <Toaster position="bottom-right" />
      </CartProvider>
    </QueryClientProvider>
  );
}
