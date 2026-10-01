import { useQuery } from "@tanstack/react-query";
import { Link, createFileRoute } from "@tanstack/react-router";
import {
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Flame,
  Percent,
  ShieldCheck,
  Sparkles,
  Star,
  Truck,
  Zap,
} from "lucide-react";
import { useState, useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { ProductCard } from "@/components/storefront/ProductCard";
import { api, type Product } from "@/services/api";

import heroImg from "@/assets/storefront-hero.jpg";
import phoneImg from "@/assets/category-phone.jpg";
import audioImg from "@/assets/category-audio.jpg";
import laptopImg from "@/assets/category-laptop.jpg";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "POORVIKA — India’s Leading Tech Retailer & Electronics Superstore" },
      {
        name: "description",
        content:
          "Buy authentic smartphones, headphones, smartwatches, chargers, and home appliances online at Poorvika with fastest 2-hour express delivery.",
      },
      { property: "og:title", content: "POORVIKA — India’s Leading Tech Retailer" },
      {
        property: "og:description",
        content: "Explore genuine electronics with official brand warranties at lowest prices.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Home,
});

const heroSlides = [
  {
    id: 1,
    tag: "SPECIAL LAUNCH",
    title: "iPhone 18 PRO",
    subtitle: "AVAILABLE NOW",
    desc: "Titanium design, breakthrough camera performance, and ultra-fast next-gen intelligence.",
    bgGradient: "from-neutral-900 via-neutral-950 to-black text-white",
    ctaText: "AVAILABLE NOW",
    ctaLink: "/products",
    category: "Accessories",
    image: phoneImg,
  },
  {
    id: 2,
    tag: "STUDIO ACOUSTICS",
    title: "Pure Sound & Deep Bass",
    subtitle: "UP TO 40% OFF",
    desc: "Discover Sony, Philips, and premium wireless earphones crafted for true audiophiles.",
    bgGradient: "from-blue-950 via-slate-900 to-slate-950 text-white",
    ctaText: "EXPLORE AUDIO",
    ctaLink: "/products",
    category: "Audio",
    image: audioImg,
  },
  {
    id: 3,
    tag: "ENERGY SAVING 2026",
    title: "Smart Kitchen & Home",
    subtitle: "FESTIVAL SAVINGS",
    desc: "Air coolers, mixers, grinders, and smart home essentials for modern everyday living.",
    bgGradient: "from-amber-950 via-stone-900 to-neutral-950 text-white",
    ctaText: "SHOP APPLIANCES",
    ctaLink: "/products",
    category: "Appliances",
    image: laptopImg,
  },
];

function Home() {
  // Query 50 real PostgreSQL products from the backend catalog
  const { data: allProducts = [], isLoading } = useQuery({
    queryKey: ["homepage-products"],
    queryFn: () => api.getProducts({ limit: 50 }),
  });

  // Hero carousel active slide state
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isPaused, setIsPaused] = useState(false);

  // Auto rotation every 5.5 seconds
  useEffect(() => {
    if (isPaused) return;
    const interval = setInterval(() => {
      setCurrentSlide((prev) => (prev + 1) % heroSlides.length);
    }, 5500);
    return () => clearInterval(interval);
  }, [isPaused]);

  const prevSlide = () => {
    setCurrentSlide((prev) => (prev - 1 + heroSlides.length) % heroSlides.length);
  };

  const nextSlide = () => {
    setCurrentSlide((prev) => (prev + 1) % heroSlides.length);
  };

  // Curate real product sections from database
  const trendingProducts = useMemo(() => {
    return allProducts.slice(0, 4);
  }, [allProducts]);

  const bestDeals = useMemo(() => {
    return allProducts
      .filter((p) => (p.discount && p.discount > 0) || (p.originalPrice && p.originalPrice > p.price))
      .slice(0, 4);
  }, [allProducts]);

  const accessories = useMemo(() => {
    return allProducts
      .filter((p) =>
        ["Data Cables", "Battery Chargers", "Cases & Covers", "Power Banks", "Pendrives", "Headphones"].includes(
          p.category ?? "",
        ),
      )
      .slice(0, 4);
  }, [allProducts]);

  const appliances = useMemo(() => {
    return allProducts
      .filter((p) =>
        ["Air Coolers", "Air Fryers", "Fans", "Irons", "Mixers Grinders & Juicers", "Voltage Stabilizers", "Voltage Stabilizer"].includes(
          p.category ?? "",
        ),
      )
      .slice(0, 4);
  }, [allProducts]);

  return (
    <div className="min-h-screen bg-[#f4f5f8] pb-16">
      {/* ============================================================ */}
      {/* 4 & 5. MAIN HERO CAROUSEL                                    */}
      {/* ============================================================ */}
      <section
        className="relative w-full overflow-hidden bg-black"
        onMouseEnter={() => setIsPaused(true)}
        onMouseLeave={() => setIsPaused(false)}
        aria-label="Main Hero Carousel"
      >
        <div
          className="flex transition-transform duration-700 ease-out"
          style={{ transform: `translateX(-${currentSlide * 100}%)` }}
        >
          {heroSlides.map((slide, idx) => (
            <div
              key={slide.id}
              className={`relative min-w-full shrink-0 bg-gradient-to-r ${slide.bgGradient}`}
            >
              <div className="mx-auto flex min-h-[360px] sm:min-h-[440px] md:min-h-[480px] max-w-[1400px] items-center justify-between px-6 py-10 sm:px-12 lg:px-16">
                {/* Slide Left Info */}
                <div className="z-10 max-w-xl space-y-4">
                  <div className="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-[11px] font-black tracking-wider uppercase text-amber-300 backdrop-blur-xs">
                    <Sparkles className="size-3.5" />
                    {slide.tag}
                  </div>

                  <h1 className="text-3xl sm:text-5xl lg:text-6xl font-black tracking-tight text-white leading-[1.08]">
                    {slide.title}
                  </h1>

                  <p className="text-lg sm:text-2xl font-extrabold text-[#ff5500] tracking-wide">
                    {slide.subtitle}
                  </p>

                  <p className="max-w-md text-xs sm:text-sm text-neutral-300 leading-relaxed">
                    {slide.desc}
                  </p>

                  <div className="pt-2">
                    <Button
                      size="lg"
                      asChild
                      className="rounded-full bg-white text-black hover:bg-neutral-100 font-extrabold text-xs sm:text-sm px-7 shadow-lg transition-transform active:scale-95"
                    >
                      <Link to={slide.ctaLink} search={{ category: slide.category }}>
                        {slide.ctaText}
                      </Link>
                    </Button>
                  </div>
                </div>

                {/* Slide Right Image */}
                <div className="relative hidden md:flex items-center justify-center max-w-md lg:max-w-lg">
                  <div className="absolute size-72 sm:size-96 rounded-full bg-white/5 blur-2xl" />
                  <img
                    src={slide.image}
                    alt={slide.title}
                    className="relative z-10 max-h-[380px] w-auto object-contain drop-shadow-2xl transition duration-500 hover:scale-105"
                  />
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Carousel Left / Right Arrow Controls */}
        <button
          type="button"
          onClick={prevSlide}
          className="absolute left-3 top-1/2 -translate-y-1/2 grid size-10 place-items-center rounded-full bg-black/40 text-white backdrop-blur-xs transition hover:bg-black/80 active:scale-90 z-20 cursor-pointer"
          aria-label="Previous slide"
        >
          <ChevronLeft className="size-6" />
        </button>
        <button
          type="button"
          onClick={nextSlide}
          className="absolute right-3 top-1/2 -translate-y-1/2 grid size-10 place-items-center rounded-full bg-black/40 text-white backdrop-blur-xs transition hover:bg-black/80 active:scale-90 z-20 cursor-pointer"
          aria-label="Next slide"
        >
          <ChevronRight className="size-6" />
        </button>

        {/* Bottom Pagination Dots */}
        <div className="absolute bottom-4 inset-x-0 flex justify-center gap-2 z-20">
          {heroSlides.map((_, dotIdx) => (
            <button
              key={dotIdx}
              type="button"
              onClick={() => setCurrentSlide(dotIdx)}
              className={`h-2.5 rounded-full transition-all cursor-pointer ${
                currentSlide === dotIdx ? "w-8 bg-[#ff5500]" : "w-2.5 bg-white/40 hover:bg-white/70"
              }`}
              aria-label={`Go to slide ${dotIdx + 1}`}
            />
          ))}
        </div>
      </section>

      {/* ============================================================ */}
      {/* 6. SECOND PROMOTIONAL BANNER                                 */}
      {/* ============================================================ */}
      <section className="mx-auto max-w-[1400px] px-4 sm:px-6 lg:px-8 mt-6">
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-gradient-to-r from-neutral-100 via-stone-50 to-neutral-200 p-6 sm:p-10 shadow-xs">
          <div className="grid items-center gap-8 md:grid-cols-2">
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-black uppercase tracking-widest text-[#ff5500]">
                  PRO FURTHER.
                </span>
                <span className="size-1 rounded-full bg-[#ff5500]" />
                <span className="text-xs font-bold text-gray-500">2026 LINEUP</span>
              </div>
              <h2 className="text-2xl sm:text-4xl font-black text-gray-900 leading-tight">
                Powerful Performance.
                <br />
                Advanced Possibilities.
              </h2>
              <p className="text-xs sm:text-sm text-gray-600 max-w-lg leading-relaxed">
                Built to take everything further with industry-leading battery efficiency, precision
                acoustics, and seamless device interoperability.
              </p>
              <div className="pt-2">
                <Button
                  size="lg"
                  asChild
                  className="rounded-full bg-black text-white hover:bg-neutral-800 px-8 font-bold text-xs tracking-wider"
                >
                  <Link to="/products" search={{ category: "Accessories" }}>
                    Explore Now
                  </Link>
                </Button>
              </div>
            </div>

            <div className="flex justify-center md:justify-end">
              <img
                src={heroImg}
                alt="Pro flagship lineup"
                className="max-h-[220px] sm:max-h-[280px] w-auto object-contain rounded-lg drop-shadow-md"
              />
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/* TRUST STRIP (Poorvika 100% Genuine, 2hr delivery)            */}
      {/* ============================================================ */}
      <section className="mx-auto max-w-[1400px] px-4 sm:px-6 lg:px-8 mt-6">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 rounded-xl border border-gray-200 bg-white p-4 shadow-2xs">
          <div className="flex items-center gap-3 p-2">
            <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-orange-50 text-[#ff5500]">
              <Truck className="size-5" />
            </div>
            <div>
              <p className="text-xs font-black uppercase text-gray-900">2-Hour Delivery</p>
              <p className="text-[11px] text-gray-500">Express doorstep dispatch</p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-2">
            <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-orange-50 text-[#ff5500]">
              <ShieldCheck className="size-5" />
            </div>
            <div>
              <p className="text-xs font-black uppercase text-gray-900">100% Genuine</p>
              <p className="text-[11px] text-gray-500">Authorized brand warranty</p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-2">
            <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-orange-50 text-[#ff5500]">
              <Percent className="size-5" />
            </div>
            <div>
              <p className="text-xs font-black uppercase text-gray-900">Best Prices</p>
              <p className="text-[11px] text-gray-500">Unbeatable electronics deals</p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-2">
            <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-orange-50 text-[#ff5500]">
              <Zap className="size-5" />
            </div>
            <div>
              <p className="text-xs font-black uppercase text-gray-900">ShopAI Assistant</p>
              <p className="text-[11px] text-gray-500">Real-time catalog lookup</p>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/* 8. PRODUCT SECTIONS (Using Real PostgreSQL Database Rows)    */}
      {/* ============================================================ */}

      {/* Section 1: Trending Products */}
      <section className="mx-auto max-w-[1400px] px-4 sm:px-6 lg:px-8 mt-10">
        <div className="mb-4 flex items-center justify-between border-b border-gray-200 pb-3">
          <div className="flex items-center gap-2">
            <Flame className="size-5 text-[#ff5500]" />
            <h2 className="text-lg sm:text-xl font-black tracking-tight text-gray-900">
              Trending Products
            </h2>
          </div>
          <Link
            to="/products"
            search={{}}
            className="flex items-center gap-1 text-xs font-bold text-[#ff5500] hover:underline"
          >
            View All <ArrowRight className="size-3.5" />
          </Link>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-80 animate-pulse rounded-lg bg-gray-200" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:gap-5 sm:grid-cols-4">
            {trendingProducts.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        )}
      </section>

      {/* Section 2: Best Deals & Offers */}
      <section className="mx-auto max-w-[1400px] px-4 sm:px-6 lg:px-8 mt-10">
        <div className="mb-4 flex items-center justify-between border-b border-gray-200 pb-3">
          <div className="flex items-center gap-2">
            <Percent className="size-5 text-[#ff5500]" />
            <h2 className="text-lg sm:text-xl font-black tracking-tight text-gray-900">
              Best Deals & Festival Offers
            </h2>
          </div>
          <Link
            to="/products"
            search={{ sort: "discount_desc" }}
            className="flex items-center gap-1 text-xs font-bold text-[#ff5500] hover:underline"
          >
            View All Offers <ArrowRight className="size-3.5" />
          </Link>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:gap-5 sm:grid-cols-4">
          {bestDeals.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      </section>

      {/* Section 3: Popular Mobiles & Top Accessories */}
      <section className="mx-auto max-w-[1400px] px-4 sm:px-6 lg:px-8 mt-10">
        <div className="mb-4 flex items-center justify-between border-b border-gray-200 pb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="size-5 text-[#ff5500]" />
            <h2 className="text-lg sm:text-xl font-black tracking-tight text-gray-900">
              Top Accessories & Audio
            </h2>
          </div>
          <Link
            to="/products"
            search={{ category: "Accessories" }}
            className="flex items-center gap-1 text-xs font-bold text-[#ff5500] hover:underline"
          >
            Browse Accessories <ArrowRight className="size-3.5" />
          </Link>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:gap-5 sm:grid-cols-4">
          {accessories.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      </section>

      {/* Section 4: Home & Kitchen Appliances */}
      <section className="mx-auto max-w-[1400px] px-4 sm:px-6 lg:px-8 mt-10">
        <div className="mb-4 flex items-center justify-between border-b border-gray-200 pb-3">
          <div className="flex items-center gap-2">
            <Zap className="size-5 text-[#ff5500]" />
            <h2 className="text-lg sm:text-xl font-black tracking-tight text-gray-900">
              Kitchen & Home Appliances
            </h2>
          </div>
          <Link
            to="/products"
            search={{ category: "Appliances" }}
            className="flex items-center gap-1 text-xs font-bold text-[#ff5500] hover:underline"
          >
            Explore Appliances <ArrowRight className="size-3.5" />
          </Link>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:gap-5 sm:grid-cols-4">
          {appliances.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      </section>
    </div>
  );
}
