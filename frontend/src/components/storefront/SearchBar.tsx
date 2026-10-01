import { useNavigate } from "@tanstack/react-router";
import { Search } from "lucide-react";
import { type FormEvent, useState } from "react";

export function SearchBar({
  initialValue = "",
  compact = false,
}: {
  initialValue?: string;
  compact?: boolean;
}) {
  const [value, setValue] = useState(initialValue);
  const navigate = useNavigate();

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const query = value.trim();
    void navigate({ to: "/products", search: query ? { q: query } : {} });
  };

  return (
    <form
      onSubmit={submit}
      className={compact ? "relative w-full" : "relative w-full max-w-2xl"}
      role="search"
    >
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Search for Products, Brands, Offers"
        aria-label="Search products, brands, offers"
        className="h-10 w-full rounded-md bg-white pl-4 pr-11 text-xs sm:text-sm text-gray-900 placeholder:text-gray-500 shadow-sm outline-none transition focus:ring-2 focus:ring-black/10"
      />
      <button
        type="submit"
        aria-label="Submit search"
        className="absolute right-0 top-0 grid h-10 w-11 place-items-center text-gray-800 transition hover:text-black cursor-pointer"
      >
        <Search className="size-4.5 stroke-[2.2]" />
      </button>
    </form>
  );
}
