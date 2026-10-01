import { Link } from "@tanstack/react-router";

export const navigationCategories = [
  { label: "Mobiles & Accessories", category: "Accessories" },
  { label: "Computers & Tablets", category: "Computers & Tablets" },
  { label: "TV & Audio", category: "Audio" },
  { label: "Kitchen Appliances", category: "Kitchen Appliances" },
  { label: "Home Appliances", category: "Appliances" },
  { label: "Smart Technology", category: "Smart Watches" },
  { label: "Personal & Health Care", category: "Personal & Health Care" },
];

export const categories = [
  "Accessories",
  "Audio",
  "Smart Watches",
  "Appliances",
  "Kitchen Appliances",
  "Computers & Tablets",
  "Personal & Health Care",
];

export function CategoryNav() {
  return (
    <nav
      className="w-full bg-white border-b border-gray-200 shadow-2xs"
      aria-label="Category Navigation"
    >
      <div className="mx-auto flex max-w-[1400px] items-center justify-between overflow-x-auto px-4 sm:px-6 lg:px-8 scrollbar-none">
        {navigationCategories.map(({ label, category }) => (
          <Link
            key={label}
            to="/products"
            search={{ category }}
            className="group relative flex h-10 shrink-0 items-center px-3 text-xs sm:text-[13px] font-bold text-gray-800 transition hover:text-[#ff5500] whitespace-nowrap"
          >
            <span>{label}</span>
            <span className="absolute inset-x-2 bottom-0 h-0.5 scale-x-0 bg-[#ff5500] transition-transform duration-200 group-hover:scale-x-100" />
          </Link>
        ))}
      </div>
    </nav>
  );
}
