import poorvikaIcon from "@/assets/poorvika-peacock.png";
import { Link } from "@tanstack/react-router";
import { ShieldCheck, Truck, Headphones, RotateCcw } from "lucide-react";

export function SiteFooter() {
  return (
    <footer className="mt-16 border-t border-border bg-card text-foreground">
      {/* Feature banner */}
      <div className="border-b border-border/70 bg-muted/30">
        <div className="mx-auto grid max-w-7xl grid-cols-2 gap-4 px-4 py-8 sm:grid-cols-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="grid size-11 place-items-center rounded-lg bg-primary/10 text-primary">
              <Truck className="size-5" />
            </div>
            <div>
              <strong className="block text-xs font-bold uppercase tracking-wider">Fast Delivery</strong>
              <span className="text-[11px] text-muted-foreground">Doorstep express dispatch</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="grid size-11 place-items-center rounded-lg bg-primary/10 text-primary">
              <ShieldCheck className="size-5" />
            </div>
            <div>
              <strong className="block text-xs font-bold uppercase tracking-wider">100% Genuine</strong>
              <span className="text-[11px] text-muted-foreground">Direct brand warranty</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="grid size-11 place-items-center rounded-lg bg-primary/10 text-primary">
              <RotateCcw className="size-5" />
            </div>
            <div>
              <strong className="block text-xs font-bold uppercase tracking-wider">Easy Returns</strong>
              <span className="text-[11px] text-muted-foreground">Hassle-free replacement</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="grid size-11 place-items-center rounded-lg bg-primary/10 text-primary">
              <Headphones className="size-5" />
            </div>
            <div>
              <strong className="block text-xs font-bold uppercase tracking-wider">Help & Support</strong>
              <span className="text-[11px] text-muted-foreground">Toll-free 1800-425-9999</span>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:grid-cols-4 sm:px-6 lg:px-8 text-sm">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="grid size-8 place-items-center rounded-lg bg-[#ff5500] p-1 shadow-xs">
              <img
                src={poorvikaIcon}
                alt="Poorvika Crest"
                className="h-full w-full object-contain"
              />
            </div>
            <span className="text-xl font-black tracking-wider uppercase text-[#ff5500] font-sans">
              POORVIKA
            </span>
          </div>
          <p className="mt-3 text-xs leading-5 text-muted-foreground">
            India’s trusted consumer electronics destination. Genuine smartphones, audio, wearables, and home appliances connected directly to verified PostgreSQL catalog.
          </p>
        </div>

        <div>
          <h2 className="text-xs font-extrabold uppercase tracking-wider text-foreground">Top Categories</h2>
          <div className="mt-3 space-y-2 text-xs text-muted-foreground">
            <Link to="/products" search={{ category: "Accessories" }} className="block hover:text-primary">
              Mobiles & Accessories
            </Link>
            <Link to="/products" search={{ category: "Audio" }} className="block hover:text-primary">
              Headphones & Audio
            </Link>
            <Link to="/products" search={{ category: "Smart Watches" }} className="block hover:text-primary">
              Smartwatches & Wearables
            </Link>
            <Link to="/products" search={{ category: "Appliances" }} className="block hover:text-primary">
              Home & Kitchen Appliances
            </Link>
          </div>
        </div>

        <div>
          <h2 className="text-xs font-extrabold uppercase tracking-wider text-foreground">Customer Service</h2>
          <div className="mt-3 space-y-2 text-xs text-muted-foreground">
            <span className="block hover:text-primary cursor-pointer">Order Tracking</span>
            <span className="block hover:text-primary cursor-pointer">Warranty Information</span>
            <span className="block hover:text-primary cursor-pointer">Store Locator</span>
            <span className="block hover:text-primary cursor-pointer">Cancellation & Returns</span>
          </div>
        </div>

        <div>
          <h2 className="text-xs font-extrabold uppercase tracking-wider text-foreground">AI Assisted Shopping</h2>
          <p className="mt-3 text-xs leading-5 text-muted-foreground">
            Need help finding the right model? Click the <strong>ShopAI Assistant</strong> at the bottom right for instant recommendations grounded in our live inventory.
          </p>
        </div>
      </div>

      <div className="border-t border-border px-4 py-4 text-center text-[11px] text-muted-foreground">
        © 2026 POORVIKA Electronics Marketplace. Powered by FastAPI, PostgreSQL, and Ollama Cloud.
      </div>
    </footer>
  );
}
