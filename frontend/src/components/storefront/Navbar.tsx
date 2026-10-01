import poorvikaIcon from "@/assets/poorvika-peacock.png";
import { Link } from "@tanstack/react-router";
import { ChevronDown, MapPin, Menu, ShoppingCart, UserRound, X, Store } from "lucide-react";
import { useState } from "react";
import { SearchBar } from "./SearchBar";
import { CategoryNav } from "./CategoryNav";
import { Button } from "@/components/ui/button";
import { useCart } from "@/context/CartContext";

export function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { totalItems, subtotal, openCart } = useCart();

  return (
    <header className="sticky top-0 z-40 w-full shadow-md">
      {/* 1. Main Solid Orange Header */}
      <div className="bg-[#ff5500] text-white">
        <div className="mx-auto flex h-16 max-w-[1400px] items-center justify-between gap-3 px-3 sm:px-5 lg:px-8">
          {/* Mobile Menu Toggle */}
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden text-white hover:bg-white/20 hover:text-white"
            onClick={() => setMobileMenuOpen((prev) => !prev)}
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? <X className="size-6" /> : <Menu className="size-6" />}
          </Button>

          {/* LEFT: [Brand/Icon] POORVIKA */}
          <Link
            to="/"
            className="flex shrink-0 items-center gap-2.5 transition hover:opacity-95"
            aria-label="POORVIKA Home"
          >
            {/* Official Poorvika Peacock Crest Icon */}
            <img
              src={poorvikaIcon}
              alt="Poorvika Crest"
              className="h-8 sm:h-9 w-auto shrink-0 object-contain drop-shadow-xs"
            />
            <span className="text-xl sm:text-2xl font-black tracking-wider uppercase text-white font-sans drop-shadow-xs">
              POORVIKA
            </span>
          </Link>

          {/* CENTER: Large Search Bar (Desktop) */}
          <div className="hidden flex-1 justify-center px-4 md:flex max-w-2xl">
            <SearchBar />
          </div>

          {/* RIGHT: Header Actions exactly matching Poorvika reference order */}
          <div className="flex items-center gap-3 sm:gap-6 text-white text-xs">
            {/* Delivery to COIMBATORE with MapPin */}
            <div className="hidden xl:flex items-center gap-1.5 cursor-pointer hover:opacity-90">
              <div className="text-right leading-tight">
                <span className="block text-[10px] font-normal text-white/90">Delivery to</span>
                <span className="font-extrabold text-xs uppercase tracking-tight text-white">COIMBATORE</span>
              </div>
              <MapPin className="size-4 shrink-0 text-white fill-white/20" />
            </div>

            {/* Locate Stores with Chevron */}
            <div className="hidden lg:flex items-center gap-1 cursor-pointer hover:opacity-90">
              <div className="text-right leading-tight">
                <span className="block text-[10px] font-normal text-white/90">Locate</span>
                <span className="flex items-center gap-0.5 font-bold text-xs text-white">
                  Stores <ChevronDown className="size-3" />
                </span>
              </div>
            </div>

            {/* Cart: 0 Items / ₹ 0 with Cart Icon */}
            <button
              type="button"
              onClick={openCart}
              className="flex items-center gap-2 text-left cursor-pointer hover:opacity-90 transition active:scale-95"
              aria-label={`Shopping cart with ${totalItems} items`}
            >
              <div className="text-right leading-tight">
                <span className="block text-[10px] font-normal text-white/90">
                  {totalItems} {totalItems === 1 ? "Item" : "Items"}
                </span>
                <span className="font-extrabold text-xs text-white">
                  ₹ {subtotal.toLocaleString("en-IN")}
                </span>
              </div>
              <div className="relative grid size-9 place-items-center rounded-full bg-white/15">
                <ShoppingCart className="size-5 text-white" />
                {totalItems > 0 && (
                  <span className="absolute -top-1 -right-1 grid min-w-4 h-4 place-items-center rounded-full bg-white px-1 text-[9px] font-black text-[#ff5500] shadow-xs">
                    {totalItems > 99 ? "99+" : totalItems}
                  </span>
                )}
              </div>
            </button>

            {/* My Account / Sign In with Account Icon */}
            <button
              type="button"
              className="flex items-center gap-2 text-left cursor-pointer hover:opacity-90 transition"
              aria-label="My Account"
            >
              <div className="hidden sm:block text-right leading-tight">
                <span className="block text-[10px] font-normal text-white/90">My Account</span>
                <span className="font-bold text-xs text-white">Sign In</span>
              </div>
              <div className="grid size-9 place-items-center rounded-full bg-white/15">
                <UserRound className="size-5 text-white" />
              </div>
            </button>
          </div>
        </div>

        {/* Mobile Search Bar (under orange bar on mobile) */}
        <div className="px-3 pb-2.5 md:hidden">
          <SearchBar compact />
        </div>
      </div>

      {/* 2. White Category Navigation Bar */}
      <CategoryNav />

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div className="border-t border-gray-200 bg-white px-4 py-3 text-gray-900 shadow-xl lg:hidden">
          <div className="mb-3 flex items-center justify-between border-b pb-2 text-xs font-bold text-gray-500">
            <span>QUICK NAVIGATION</span>
            <div className="flex items-center gap-1 text-primary">
              <MapPin className="size-3.5" /> Coimbatore
            </div>
          </div>
          <Link
            to="/products"
            search={{}}
            onClick={() => setMobileMenuOpen(false)}
            className="block py-2 text-sm font-bold text-primary hover:underline"
          >
            Browse All Products
          </Link>
          <Link
            to="/products"
            search={{ category: "Accessories" }}
            onClick={() => setMobileMenuOpen(false)}
            className="block py-2 text-sm font-medium text-gray-700 hover:text-primary"
          >
            Mobiles & Accessories
          </Link>
          <Link
            to="/products"
            search={{ category: "Audio" }}
            onClick={() => setMobileMenuOpen(false)}
            className="block py-2 text-sm font-medium text-gray-700 hover:text-primary"
          >
            TV & Audio
          </Link>
          <Link
            to="/products"
            search={{ category: "Appliances" }}
            onClick={() => setMobileMenuOpen(false)}
            className="block py-2 text-sm font-medium text-gray-700 hover:text-primary"
          >
            Kitchen & Home Appliances
          </Link>
          <Link
            to="/products"
            search={{ category: "Smart Watches" }}
            onClick={() => setMobileMenuOpen(false)}
            className="block py-2 text-sm font-medium text-gray-700 hover:text-primary"
          >
            Smart Technology
          </Link>
          <Link
            to="/products"
            search={{ category: "Personal & Health Care" }}
            onClick={() => setMobileMenuOpen(false)}
            className="block py-2 text-sm font-medium text-gray-700 hover:text-primary"
          >
            Personal & Health Care
          </Link>
        </div>
      )}
    </header>
  );
}
