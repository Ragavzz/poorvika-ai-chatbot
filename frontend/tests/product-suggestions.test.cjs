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
    (id) => (id === "@/lib/suggestion-timing" ? { recordSuggestionTiming: () => {} } : { api }),
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
});

test("sends existing product information and displays only model strings", async () => {
  const f = fixture();
  const context = f.getProductSuggestionContext({}, product);
  assert.deepEqual(await f.getProductSuggestions(context), questions);
  assert.deepEqual(f.calls[0], {
    name: product.name,
    brand: product.brand,
    category: product.category,
    price: product.price,
    specifications: product.specifications,
  });
});

test("reuses generated questions across revisits and refreshes", async () => {
  const storage = new Map();
  const f = fixture(storage);
  const context = f.getProductSuggestionContext({}, product);
  await f.getProductSuggestions(context);
  await f.getProductSuggestions(context);
  assert.equal(f.calls.length, 1);
  const refreshed = fixture(storage);
  assert.deepEqual(await refreshed.getProductSuggestions(context), questions);
  assert.equal(refreshed.calls.length, 0);
  await f.getProductSuggestions(
    f.getProductSuggestionContext({}, { ...product, id: "other-phone", name: "Other Phone" }),
  );
  assert.equal(f.calls.length, 2);
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
