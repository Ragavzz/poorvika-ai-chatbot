const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");
const { QueryClient } = require("@tanstack/react-query");

const compiled = ts.transpileModule(
  fs.readFileSync(path.join(__dirname, "../src/lib/product-suggestions.ts"), "utf8"),
  { compilerOptions: { module: ts.ModuleKind.CommonJS } },
).outputText;
const questions = [
  "Would this phone suit daily multitasking?",
  "How does this phone compare for battery life?",
  "Which alternatives offer comparable storage?",
];
function fixture(storage = new Map()) {
  const calls = [];
  let fail = false;
  const loaded = { exports: {} };
  const api = {
    getChatSuggestions: async (product) => {
      calls.push(product);
      if (fail) throw new Error("Model unavailable");
      return { suggestions: questions };
    },
  };
  new Function("require", "module", "exports", "sessionStorage", compiled)(
    (id) =>
      id === "@/lib/suggestion-timing"
        ? { beginSuggestionTiming: () => "test-request", recordSuggestionTiming: () => {} }
        : { api },
    loaded,
    loaded.exports,
    { getItem: (key) => storage.get(key), setItem: (key, value) => storage.set(key, value) },
  );
  return {
    ...loaded.exports,
    calls,
    storage,
    fail: () => {
      fail = true;
    },
  };
}
const product = {
  id: "test-phone",
  name: "Test Phone",
  brand: "Test",
  category: "Mobiles",
  price: 7299,
  specifications: { RAM: "4GB" },
};

test("no meaningful context produces no generation context", () => {
  const f = fixture();
  assert.equal(f.getProductSuggestionContext({}), null);
  assert.equal(f.getProductSuggestionContext({ q: "  " }), null);
  assert.equal(f.getProductSuggestionContext({ category: "Mobiles", products: [] }), null);
});

test("sends existing product information and displays only model strings", async () => {
  const f = fixture();
  const context = f.getProductSuggestionContext({}, product);
  assert.deepEqual(await f.getProductSuggestions(context), questions);
  assert.deepEqual(f.calls[0], {
    id: product.id,
    name: product.name,
    brand: product.brand,
    category: product.category,
    price: product.price,
    specifications: product.specifications,
  });
});

test("category context carries actual listing results and filters without singular product context", () => {
  const f = fixture();
  const context = f.getProductSuggestionContext({
    category: "Mobiles",
    filters: { inStockOnly: true },
    products: [product, { ...product, id: "second", name: "Second Mobile" }],
  });
  assert.equal(context.product.category, "Mobiles");
  assert.equal(context.product.name, "Mobiles");
  assert.equal(context.product.products.length, 2);
  assert.equal(context.product.products[0].name, product.name);
  assert.deepEqual(context.product.filters, { inStockOnly: true });
  assert.notEqual(
    context.key,
    f.getProductSuggestionContext({ category: "Mobiles", products: [{ ...product, price: 7399 }] }).key,
  );
});

test("query identity includes product data, listing result set and model prompt configuration", () => {
  const f = fixture();
  const phone = f.getProductSuggestionContext({}, product);
  const revised = f.getProductSuggestionContext({}, { ...product, price: 7399 });
  assert.notDeepEqual(f.getSuggestionQueryKey(phone, "model-v1"), f.getSuggestionQueryKey(revised, "model-v1"));
  assert.notDeepEqual(f.getSuggestionQueryKey(phone, "model-v1"), f.getSuggestionQueryKey(phone, "model-v2"));
});

test("ignores persisted suggestions; output comes only from current provider", async () => {
  const f = fixture(
    new Map([["shopai:llm-suggestions:v1:product:test-phone", JSON.stringify(["Stale?"])]]),
  );
  const context = f.getProductSuggestionContext({}, product);
  assert.deepEqual(await f.getProductSuggestions(context), questions);
  assert.equal(f.calls.length, 1);
  f.fail();
  await assert.rejects(() => f.getProductSuggestions(context), /Model unavailable/);
});

test("query caching deduplicates concurrent requests", async () => {
  const f = fixture();
  const context = f.getProductSuggestionContext({}, product);
  const client = new QueryClient();
  const options = {
    queryKey: ["product-suggestions", context.key],
    queryFn: () => f.getProductSuggestions(context),
    staleTime: Infinity,
    retry: false,
  };
  await Promise.all([client.fetchQuery(options), client.fetchQuery(options)]);
  await client.fetchQuery(options);
  assert.equal(f.calls.length, 1);
  client.clear();
});

test("generation failure rejects without static fallback or cached questions", async () => {
  const f = fixture();
  f.fail();
  await assert.rejects(
    () => f.getProductSuggestions(f.getProductSuggestionContext({}, product)),
    /Model unavailable/,
  );
  assert.equal(f.storage.size, 0);
});
