const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");
const { QueryClient, QueryObserver, skipToken } = require("@tanstack/react-query");
const suggestionRequests = [];

function compile(file, modules, globals = {}) {
  const output = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../src", file), "utf8"), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.ReactJSX,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;
  const loaded = { exports: {} };
  new Function("require", "module", "exports", ...Object.keys(globals), output)(
    (id) => {
      if (!(id in modules)) throw Error("Unexpected module " + id);
      return modules[id];
    },
    loaded,
    loaded.exports,
    ...Object.values(globals),
  );
  return loaded.exports;
}
const local = compile("lib/product-suggestions.ts", {
  "@/lib/suggestion-timing": { beginSuggestionTiming() {}, recordSuggestionTiming() {} },
  "@/services/api": {
    api: {
      getChatSuggestions(product) {
        suggestionRequests.push(product);
        throw Error("Ollama unavailable");
      },
    },
  },
});
const jsx = { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) };
const watch = {
  id: "watch-a",
  name: "Samsung Galaxy Watch5 Pro LTE",
  category: "Smartwatches",
  price: 25000,
};
let listingContext = null;
const phone = { id: "phone-b", name: "Apple Phone", category: "Mobiles", price: 30000 };
function find(tree, predicate) {
  if (!tree || typeof tree !== "object") return null;
  if (Array.isArray(tree)) return tree.map((item) => find(item, predicate)).find(Boolean) || null;
  return predicate(tree) ? tree : find(tree.props?.children, predicate);
}

function fixture(realTimers = false, generationEnabled = true, modelError = false, staleDataOnError = false) {
  let clock = 0,
    sequence = 0,
    index = 0;
  const timers = new Map(),
    slots = [],
    queued = [],
    timing = [];
  const client = new QueryClient();
  const location = { pathname: "/products/watch-a", search: {} };
  let productId = watch.id;
  const body = {};
  function schedule(callback, delay) {
    if (realTimers) return setTimeout(callback, delay);
    const id = ++sequence;
    timers.set(id, { at: clock + delay, callback });
    return id;
  }
  function cancel(id) {
    if (realTimers) clearTimeout(id);
    else timers.delete(id);
  }
  function effect(callback, dependencies) {
    const i = index++;
    const previous = slots[i];
    if (!previous || dependencies.some((dep, j) => !Object.is(dep, previous.dependencies[j]))) {
      queued.push(() => {
        previous?.cleanup?.();
        slots[i] = { dependencies, cleanup: callback() };
      });
    }
  }
  const hooks = {
    useRef: (initial) => {
      const i = index++;
      return slots[i] ?? (slots[i] = { current: initial });
    },
    useState: (initial) => {
      const i = index++;
      if (!(i in slots)) slots[i] = initial;
      return [
        slots[i],
        (next) => {
          slots[i] = typeof next === "function" ? next(slots[i]) : next;
        },
      ];
    },
    useEffect: effect,
    useLayoutEffect: effect,
  };
  const selected = [];
  const capabilityEnabled = [];
  const suggestionEnabled = [];
  let refetchCalls = 0;
  let modelReady = true;
  let capabilityReady = true;
  const { ProductSuggestionPopup } = compile(
    "components/storefront/ProductSuggestionPopup.tsx",
    {
      react: { ...hooks, createContext: (value) => ({ _default: value }), useContext: (value) => listingContext ?? value._default },
      "react/jsx-runtime": jsx,
      "react-dom": {
        createPortal: (tree, target) => {
          assert.equal(target, body);
          return tree;
        },
      },
      "@tanstack/react-router": {
        useRouterState: ({ select }) =>
          select({ location, matches: productId ? [{ params: { productId } }] : [] }),
      },
      "@tanstack/react-query": {
        skipToken,
        useQueryClient: () => client,
        useQuery: (options) => {
          if (options.queryKey[0] === "chat-capabilities") {
            capabilityEnabled.push(options.enabled);
            return { data: capabilityReady ? { ollama_enabled: generationEnabled, model_configuration: "model-v1" } : undefined, isLoading: !capabilityReady };
          }
          if (options.queryKey[0] === "model-product-suggestions-v3") {
            suggestionEnabled.push(options.enabled);
            return {
              data:
                options.enabled && (!modelError || staleDataOnError) && modelReady
                  ? [
                      `Model question about ${productId || location.search.category}?`,
                      "Model battery question?",
                      "Model alternatives question?",
                    ]
                  : undefined,
              isError: modelError,
              isFetching: !modelReady,
              refetch: async () => {
                refetchCalls++;
                try {
                  return await options.queryFn({ signal: new AbortController().signal });
                } catch {
                  return undefined;
                }
              },
            };
          }
          assert.equal(options.queryFn, skipToken);
          return { data: client.getQueryData(options.queryKey), isError: false };
        },
      },
      "lucide-react": { Sparkles: "sparkles", X: "x" },
      "@/lib/product-suggestions": local,
      "@/services/api": { api: { getChatCapabilities() {} } },
      "@/lib/suggestion-timing": {
        beginSuggestionTiming: (key) => timing.push({ key, event: "ready", time: clock }),
        recordSuggestionTiming: (key, event) => timing.push({ key, event, time: clock }),
      },
    },
    {
      setTimeout: schedule,
      clearTimeout: cancel,
      requestAnimationFrame: (callback) => schedule(callback, 16),
      cancelAnimationFrame: cancel,
      document: { body },
    },
  );
  function render(open = false) {
    index = 0;
    const tree = ProductSuggestionPopup({
      open,
      onSelect: (text, id) => selected.push({ text, id }),
    });
    while (queued.length) queued.shift()();
    return tree;
  }
  return {
    render,
    client,
    selected,
    get refetchCalls() { return refetchCalls; },
    timing,
    capabilityEnabled,
    suggestionEnabled,
    timers,
    ready: (value) => {
      modelReady = value;
    },
    capabilitiesReady: (value) => { capabilityReady = value; },
    cache: (product) => client.setQueryData(["product", product.id], product),
    route: (id, search = {}) => {
      productId = id;
      location.pathname = id ? "/products/" + id : "/products";
      location.search = search;
    },
    listing: (products, filters = {}) => { listingContext = { listing: { products, filters }, setListing() {} }; },
    advance: (milliseconds) => {
      const end = clock + milliseconds;
      while (true) {
        const next = [...timers.entries()]
          .filter(([, timer]) => timer.at <= end)
          .sort((a, b) => a[1].at - b[1].at)[0];
        if (!next) break;
        timers.delete(next[0]);
        clock = next[1].at;
        next[1].callback();
      }
      clock = end;
    },
    close: () => {
      for (const slot of slots) slot?.cleanup?.();
      client.clear();
      listingContext = null;
    },
  };
}

test("capabilities prefetch starts when the root popup mounts, before product context is ready", () => {
  const f = fixture();
  f.route(undefined, { category: "Mobiles" });
  f.render();
  assert.notEqual(f.capabilityEnabled[0], false);
  assert.equal(f.capabilityEnabled.length, 1);
  f.close();
});

test("generation query starts as soon as context is ready without waiting for capabilities", () => {
  const f = fixture();
  f.capabilitiesReady(false);
  f.cache(watch);
  f.render();
  assert.equal(f.suggestionEnabled.at(-1), true);
  f.close();
});

test("direct refresh shows generated questions as soon as product data is ready", () => {
  const f = fixture();
  assert.equal(f.render(), null);
  f.advance(5000);
  assert.equal(f.timers.size, 0);
  f.cache(watch);
  const tree = f.render();
  assert.equal(tree, null);
  const ready = f.render();
  assert.equal(ready.type, "aside");
  assert.ok(find(ready, (node) => node.props?.children === "Need help with " + watch.name + "?"));
  assert.ok(find(ready, (node) => node.props?.children === `Model question about ${watch.id}?`));
  f.close();
});

test("route changes cancel old timers and never show old product suggestions", () => {
  const f = fixture();
  f.cache(watch);
  f.render();
  f.advance(500);
  f.route(phone.id);
  assert.equal(f.render(), null);
  assert.equal(f.timers.size, 0);
  f.cache(phone);
  f.render();
  f.advance(1200);
  const tree = f.render();
  assert.ok(find(tree, (node) => node.props?.children === "Need help with " + phone.name + "?"));
  assert.equal(
    find(tree, (node) => node.props?.children === "Need help with " + watch.name + "?"),
    null,
  );
  f.close();
});

test("dismissal survives rerenders and revisits; another product gets its own popup", () => {
  const f = fixture();
  f.cache(watch);
  f.render();
  f.advance(1200);
  find(
    f.render(),
    (node) => node.props?.["aria-label"] === "Dismiss product suggestions",
  ).props.onClick();
  for (let i = 0; i < 4; i++) {
    f.advance(5000);
    assert.equal(f.render(), null);
  }
  f.route(phone.id);
  f.cache(phone);
  f.render();
  f.advance(1200);
  assert.ok(f.render());
  f.route(watch.id);
  assert.equal(f.render(), null);
  f.advance(5000);
  assert.equal(f.render(), null);
  f.close();
});

test("manual assistant hides and consumes the proactive prompt without reopening on close", () => {
  const f = fixture();
  f.cache(watch);
  f.render();
  f.advance(400);
  assert.equal(f.render(true), null);
  assert.equal(f.timers.size, 0);
  f.render(false);
  f.advance(5000);
  assert.equal(f.render(false), null);
  f.close();
});

test("repeated renders do not schedule timers; selection uses the current product ID", () => {
  const f = fixture();
  f.cache(watch);
  for (let i = 0; i < 5; i++) f.render();
  assert.equal(f.timers.size, 1);
  const tree = f.render();
  find(
    tree,
    (node) =>
      node.type === "button" && String(node.props?.children).startsWith("Model question about"),
  ).props.onClick();
  assert.equal(f.selected[0].id, watch.id);
  assert.ok(f.selected[0].text.includes(watch.id));
  assert.equal(f.render(), null);
  f.close();
});

test("listing filters use immediate context; layout is portaled, fixed and viewport bounded", () => {
  const f = fixture();
  f.route(undefined, { category: "Smartwatches" });
  f.listing([watch], { inStockOnly: true });
  f.render();
  f.advance(1200);
  const tree = f.render();
  assert.ok(tree);
  assert.match(tree.props.className, /fixed.*z-50/);
  assert.match(tree.props.className, /100vw-2rem/);
  assert.match(tree.props.className, /100dvh-7rem/);
  assert.match(tree.props.className, /overflow-y-auto/);
  f.close();
});

test("real React Query observer receives page data without a duplicate request", async () => {
  const client = new QueryClient();
  let calls = 0;
  const key = ["product", watch.id];
  const observer = new QueryObserver(client, { queryKey: key, queryFn: skipToken });
  const seen = [];
  const unsubscribe = observer.subscribe((result) => seen.push(result.data));
  await client.fetchQuery({
    queryKey: key,
    queryFn: async () => {
      calls++;
      return watch;
    },
  });
  assert.equal(calls, 1);
  assert.ok(seen.includes(watch));
  unsubscribe();
  client.clear();
});

test("loading and generated popup render without an artificial timer (not a browser paint test)", () => {
  const f = fixture(true);
  f.cache(watch);
  const start = performance.now();
  f.render();
  assert.ok(f.render());
  const elapsed = performance.now() - start;
  console.log("Measured Node context-to-popup-render: " + elapsed.toFixed(1) + " ms");
  assert.ok(elapsed < 100);
  f.close();
});

for (const error of [false, true])
  test("no fixed popup when generation disabled or failed: " + error, () => {
    const f = fixture(false, error, error);
    f.cache(watch);
    f.render();
    f.advance(5000);
    const tree = f.render();
    if (error) assert.ok(find(tree, (node) => node.props?.children === "Try again"));
    else assert.equal(tree, null);
    f.close();
  });

test("slow generation does not record a paint or show questions before real output arrives", () => {
  const f = fixture();
  f.cache(watch);
  f.ready(false);
  f.render();
  f.advance(10000);
  const loading = f.render();
  assert.ok(find(loading, (node) => node.props?.role === "status"));
  assert.equal(find(loading, (node) => String(node.props?.children).startsWith("Model question")), null);
  assert.equal(
    f.timing.some((event) => event.event === "visible"),
    false,
  );
  f.ready(true);
  assert.ok(f.render());
  f.advance(32);
  assert.equal(f.timing.filter((event) => event.event === "visible").length, 1);
  f.close();
});

test("failed listing retry sends a fresh current-context request and hides stale questions", async () => {
  suggestionRequests.length = 0;
  const f = fixture(false, true, true, true);
  f.route(undefined, { category: "Mobiles" });
  const mobiles = [
    phone,
    { ...phone, id: "phone-c", name: "Samsung Galaxy A16", price: 15999 },
  ];
  const filters = { maxPrice: 150000, inStockOnly: false, minRating: 0, minDiscount: 0, brands: [], page: 1 };
  f.listing(mobiles, filters);
  f.render();
  f.advance(1200);
  const failed = f.render();
  assert.ok(find(failed, (node) => node.props?.children === "Suggestions could not be generated."));
  assert.equal(find(failed, (node) => String(node.props?.children).startsWith("Model question")), null);
  const retry = find(failed, (node) => node.type === "button" && node.props?.children === "Try again");
  assert.ok(retry);
  await retry.props.onClick();
  assert.equal(f.refetchCalls, 1);
  assert.equal(suggestionRequests.length, 1);
  assert.equal(suggestionRequests[0].category, "Mobiles");
  assert.deepEqual(suggestionRequests[0].filters, filters);
  assert.deepEqual(suggestionRequests[0].products.map((item) => item.id), ["phone-b", "phone-c"]);
  assert.equal(find(f.render(), (node) => String(node.props?.children).startsWith("Model question")), null);
  f.close();
});

test("reported iPhone 15 context and navigation to watch work without remount", () => {
  const f = fixture();
  const iphone = {
    id: "apple-iphone-15-black-256gb",
    name: "Apple iPhone 15 (Black,256GB)",
    category: "Mobiles",
    price: 69900,
  };
  f.route(iphone.id);
  f.cache(iphone);
  f.render();
  f.advance(1200);
  assert.ok(
    find(f.render(), (node) => node.props?.children === "Need help with " + iphone.name + "?"),
  );
  f.route(watch.id);
  f.cache(watch);
  assert.equal(f.render(), null);
  f.advance(1200);
  assert.ok(
    find(f.render(), (node) => node.props?.children === "Need help with " + watch.name + "?"),
  );
  f.close();
});
