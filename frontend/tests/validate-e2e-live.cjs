// Explicit live QA runner, separate from isolated *.test.cjs tests.
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const ts = require("typescript");
const root = path.resolve(__dirname, "../..");
const base = "http://127.0.0.1:8000";
const catalog = JSON.parse(
  fs.readFileSync(path.join(root, "documentation/e2e-catalog-snapshot.json"), "utf8"),
);
const records = [],
  popup = [];
const report = {
  generated_at: new Date().toISOString(),
  catalog_rows: catalog.length,
  execution:
    "Live HTTP services plus actual React CartProvider and chat handlers in a Node hook harness; no browser",
  records,
  popup,
};
function save() {
  fs.writeFileSync(
    path.join(root, "documentation/e2e-live-results.json"),
    JSON.stringify(report, null, 2),
  );
}
function load(file, modules = {}, globals = {}) {
  const module = { exports: {} };
  const output = ts.transpileModule(
    fs.readFileSync(path.join(root, "frontend/src", file), "utf8"),
    {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        jsx: ts.JsxEmit.ReactJSX,
        target: ts.ScriptTarget.ES2022,
      },
    },
  ).outputText;
  new Function("require", "module", "exports", ...Object.keys(globals), output)(
    (id) => {
      if (id in modules) return modules[id];
      if (id === "react/jsx-runtime") return jsx;
      if (id === "lucide-react") return { MessageCircle: "icon", X: "x" };
      if (id.startsWith("@/components/")) return new Proxy({}, { get: (_, key) => String(key) });
      throw Error("Unexpected module " + id);
    },
    module,
    module.exports,
    ...Object.values(globals),
  );
  return module.exports;
}
const jsx = { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) };
function hooks() {
  let index = 0;
  const slots = [],
    effects = [];
  const api = {
    createContext: () => ({ Provider: "provider" }),
    useState: (initial) => {
      const i = index++;
      if (!(i in slots)) slots[i] = typeof initial === "function" ? initial() : initial;
      return [
        slots[i],
        (next) => {
          slots[i] = typeof next === "function" ? next(slots[i]) : next;
        },
      ];
    },
    useRef: (initial) => {
      const i = index++;
      return slots[i] ?? (slots[i] = { current: initial });
    },
    useEffect: (fn) => {
      index++;
      effects.push(fn);
    },
    useMemo: (fn) => {
      index++;
      return fn();
    },
    useCallback: (fn) => {
      index++;
      return fn;
    },
    lazy: () => "panel",
    Suspense: "suspense",
  };
  return {
    api: { ...api, default: api },
    render: (component, props) => {
      index = 0;
      effects.length = 0;
      return component(props);
    },
    effects: () => [...effects],
  };
}
const stateLib = load("lib/cart-state.ts");
const cartLib = load("lib/chat-cart.ts");
const storageMap = new Map();
const storage = {
  getItem: (key) => storageMap.get(key) || null,
  setItem: (key, value) => storageMap.set(key, value),
};
const cartHooks = hooks();
const { CartProvider } = load(
  "context/CartContext.tsx",
  { react: cartHooks.api, sonner: { toast: { error() {} } }, "@/lib/cart-state": stateLib },
  {
    window: { localStorage: storage, addEventListener() {}, removeEventListener() {} },
    localStorage: storage,
  },
);
let cart;
function renderCart() {
  const tree = cartHooks.render(CartProvider, { children: null });
  cart = { ...tree.props.value, ...tree.props.children.props.value };
  for (const effect of cartHooks.effects()) effect();
  return cart;
}
renderCart();
async function getProduct(id) {
  const response = await fetch(base + "/api/products/" + encodeURIComponent(id));
  assert.equal(response.status, 200);
  return response.json();
}
async function raw(message) {
  const started = performance.now();
  const response = await fetch(base + "/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-ShopAI-Request-ID": crypto.randomUUID() },
    body: JSON.stringify({ message }),
    signal: AbortSignal.timeout(90000),
  });
  const payload = await response.json();
  const text = payload.response ?? payload.detail ?? "";
  const ids =
    text
      .match(/\[\[SHOPAI_PRODUCTS:([^\]]*)\]\]/)?.[1]
      .split(",")
      .filter(Boolean) ?? [];
  const rows = ids.map((id) => catalog.find((p) => p.id === id));
  const record = {
    input: message.split("\n\n<shopai_client_context>")[0],
    http_status: response.status,
    latency_ms: performance.now() - started,
    response: text,
    response_source: payload.response_source,
    timings: JSON.parse(response.headers.get("X-ShopAI-Chat-Timing") || "null"),
    product_ids: ids,
    database_rows: rows,
    status: "UNREVIEWED",
  };
  records.push(record);
  save();
  return { record, text, ids, rows, payload };
}
const stamp = Date.now();
const session = (label) => "e2e-" + label + "-" + stamp;
async function ask(text, label = "main", extra = {}) {
  renderCart();
  const context = {
    session_id: session(label),
    cart: cart.items.map(({ product, quantity }) => ({
      id: product.id,
      name: product.name,
      price: product.price,
      quantity,
    })),
    ...extra,
  };
  return raw(
    text + "\n\n<shopai_client_context>" + JSON.stringify(context) + "</shopai_client_context>",
  );
}
function pass(result, check) {
  try {
    check(result);
    result.record.status = "PASS";
  } catch (error) {
    result.record.status = "FAIL";
    result.record.failure = error.message;
  }
  save();
  console.log(result.record.status, result.record.input);
}
function grounded(r) {
  assert.equal(r.record.http_status, 200);
  assert.ok(r.ids.length);
  assert.ok(r.rows.every(Boolean));
  for (const row of r.rows) {
    assert.ok(r.text.includes(row.name));
    assert.ok(r.text.includes(Number(row.price).toLocaleString("en-US")));
  }
}
async function apply(r) {
  const before = JSON.parse(JSON.stringify(renderCart().items));
  const visible = await cartLib.applyChatCartResponse(
    r.text,
    {
      getItems: () => renderCart().items,
      addToCart: (...args) => renderCart().addToCart(...args),
      removeFromCart: (...args) => renderCart().removeFromCart(...args),
      updateQuantity: (...args) => renderCart().updateQuantity(...args),
    },
    getProduct,
  );
  const after = renderCart();
  r.record.cart_execution = {
    before,
    after: JSON.parse(JSON.stringify(after.items)),
    subtotal: after.subtotal,
    total_items: after.totalItems,
    client_confirmation: visible,
    persisted: JSON.parse(storage.getItem(stateLib.CART_STORAGE_KEY)),
  };
  save();
  return after;
}
function find(tree, predicate) {
  if (!tree || typeof tree !== "object") return null;
  if (Array.isArray(tree)) return tree.map((n) => find(n, predicate)).find(Boolean);
  return predicate(tree) ? tree : find(tree.props?.children, predicate);
}
async function main() {
  report.health = await (await fetch(base + "/api/health")).json();
  assert.equal(report.health.decision_provider, "laya");
  assert.equal(report.health.ollama_enabled, true);
  assert.equal(report.health.database.type, "PostgreSQL");
  assert.equal(report.health.database.connected, true);
  report.frontend_http_status = (await fetch("http://localhost:8080")).status;
  save();
  for (const text of ["Hi", "Hello", "Good morning"])
    pass(await ask(text, "greeting"), (r) => {
      assert.equal(r.record.http_status, 200);
      assert.equal(r.record.response_source, "ollama");
      assert.equal(r.record.timings.ollama_call_count, 1);
      assert.doesNotMatch(r.text, /no matching catalog|unavailable/i);
    });
  pass(await ask("Show me Sony earphones under 1000 rupees", "sony"), (r) => {
    grounded(r);
    assert.ok(r.rows.every((p) => p.brand === "Sony" && p.price <= 1000));
  });
  const phones = await ask("Show me Samsung phones under 20000", "phones");
  pass(phones, (r) => {
    grounded(r);
    assert.ok(
      r.rows.every((p) => p.brand === "Samsung" && p.category === "Mobiles" && p.price <= 20000),
    );
  });
  pass(await ask("Show me laptops", "laptops"), (r) => {
    grounded(r);
    assert.ok(r.rows.every((p) => p.category === "Computers"));
  });
  if (phones.ids.length >= 2) {
    pass(await ask("Compare these two phones", "phones"), (r) => {
      assert.equal(r.record.response_source, "deterministic_comparison");
      if (phones.ids.length > 2) {
        assert.match(r.text, /Which two/);
        assert.doesNotMatch(r.text, /\| Price \|/);
      } else assert.ok(phones.rows.every((p) => r.text.includes(p.name)));
    });
    pass(await ask("Compare the first two phones", "phones"), (r) => {
      assert.ok(r.text.includes("| Price |"));
      assert.ok(phones.rows.slice(0, 2).every((p) => r.text.includes(p.name)));
      assert.ok(phones.rows.slice(2).every((p) => !r.text.includes(p.name)));
    });
  }
  const selected = phones.ids[0];
  pass(await ask("Tell me about the first product", "phones"), (r) => {
    grounded(r);
    assert.equal(r.ids[0], selected);
  });
  pass(await ask("Tell me the specifications of this product", "phones"), (r) => {
    grounded(r);
    const p = catalog.find((p) => p.id === selected);
    assert.ok(Object.values(p.flattened_specs || {}).some((v) => r.text.includes(String(v))));
  });
  pass(await ask("What is its price?", "phones"), (r) => {
    grounded(r);
    assert.equal(r.ids[0], selected);
  });
  pass(await ask("Suggest a phone for photography", "recommend"), (r) => {
    grounded(r);
    assert.equal(r.record.response_source, "deterministic_recommendation");
    assert.ok(r.rows.every((p) => p.category === "Mobiles"));
    assert.match(r.text, /don't have verified performance/i);
  });
  pass(await ask("Is there a cheaper alternative?", "phones"), (r) => {
    assert.equal(r.record.http_status, 200);
    assert.equal(r.record.timings.resolved_action, "product_search");
    if (r.ids.length) {
      grounded(r);
      assert.ok(
        r.rows.every(
          (p) =>
            p.id !== selected &&
            p.price < catalog.find((p) => p.id === selected).price &&
            p.brand === "Samsung",
        ),
      );
    } else assert.match(r.text, /couldn't find|no matching/i);
  });
  let added = await ask("Add this product to my cart", "cart", {
    suggestion_product_id: selected,
    recent_product_ids: [selected],
  });
  await apply(added);
  pass(added, () => {
    assert.equal(cart.items.length, 1);
    assert.equal(cart.items[0].product.id, selected);
    assert.equal(cart.items[0].quantity, 1);
  });
  const increased = await ask("Increase the quantity to two", "cart");
  await apply(increased);
  pass(increased, () => assert.equal(cart.items[0]?.quantity, 2));
  pass(await ask("What is my current total?", "cart"), (r) => {
    assert.ok(r.text.includes("₹" + cart.subtotal.toLocaleString("en-IN")));
    assert.ok(r.text.includes("2 items"));
  });
  const decreased = await ask("Reduce the quantity to one", "cart");
  await apply(decreased);
  pass(decreased, () => assert.equal(cart.items[0]?.quantity, 1));
  const removed = await ask("Remove this product from my cart", "cart");
  await apply(removed);
  pass(removed, () => assert.equal(cart.items.length, 0));
  pass(await ask("Show me my cart", "cart"), (r) => assert.match(r.text, /empty/i));
  const unavailable = catalog.find((p) => !p.in_stock || p.stock === 0);
  if (unavailable) {
    const r = await ask("Add this product to my cart", "outstock", {
      suggestion_product_id: unavailable.id,
      recent_product_ids: [unavailable.id],
    });
    await apply(r);
    pass(r, () => {
      assert.doesNotMatch(r.text, /SHOPAI_ADD_TO_CART/);
      assert.match(r.text, /out of stock/i);
      assert.equal(cart.items.length, 0);
    });
  }
  pass(await ask("Show me Samsung phones under 1 rupee", "zero"), (r) => {
    assert.equal(r.ids.length, 0);
    assert.match(r.text, /couldn't find|no matching/i);
  });
  pass(await ask("Show me nonexistentmodelxyz123", "invalid"), (r) => {
    assert.equal(r.ids.length, 0);
    assert.doesNotMatch(r.text, /SHOPAI_ADD_TO_CART/);
  });
  pass(await ask("Tell me about this product", "ambiguous"), (r) =>
    assert.match(r.text, /which product|choose/i),
  );
  const popupIds = [
    "apple-iphone-15-black-256gb",
    selected,
    "samsung-galaxy-watch5-pro-lte-45-mm-gray-titanium-sm-r925fztainu",
  ];
  for (const id of popupIds) {
    const product = await getProduct(id);
    const ctx = {
      id: product.id,
      name: product.name,
      brand: product.brand,
      category: product.category,
      price: product.price,
      description: product.description?.slice(0, 4000),
      specifications: product.specifications,
    };
    const start = performance.now();
    const response = await fetch(base + "/api/chat/suggestions", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-ShopAI-Request-ID": crypto.randomUUID() },
      body: JSON.stringify({ product: ctx }),
      signal: AbortSignal.timeout(60000),
    });
    const payload = await response.json();
    const result = {
      product_id: id,
      context: ctx,
      http_status: response.status,
      latency_ms: performance.now() - start,
      payload,
      timings: JSON.parse(response.headers.get("X-ShopAI-Suggestion-Timing") || "null"),
      status: response.ok ? "REVIEW_RELEVANCE" : "FAIL",
    };
    popup.push(result);
    save();
    console.log("POPUP", id, response.status);
  }
  const genuine = popup.find((p) => p.http_status === 200);
  if (genuine) {
    const outer = hooks();
    const { Chatbot } = load("components/storefront/Chatbot.tsx", {
      react: outer.api,
      "./ProductSuggestionPopup": { ProductSuggestionPopup: "popup" },
    });
    let tree = outer.render(Chatbot);
    find(tree, (n) => n.type === "popup").props.onSelect(
      genuine.payload.suggestions[0],
      genuine.product_id,
    );
    tree = outer.render(Chatbot);
    const props = find(tree, (n) => n.type === "panel").props;
    assert.equal(props.open, true);
    const inner = hooks();
    let pending;
    const { ChatbotPanel } = load("components/storefront/ChatbotPanel.tsx", {
      react: inner.api,
      "@/services/api": {
        api: {
          chat: (message) => {
            pending = raw(message);
            return pending.then((r) => r.text);
          },
          getProduct,
        },
      },
      "@/context/CartContext": { useCart: () => renderCart() },
      "@/lib/shopping-response": { formatShoppingResponse: (text) => text },
      "@/lib/chat-cart": cartLib,
    });
    inner.render(ChatbotPanel, props);
    for (const effect of inner.effects()) effect();
    const clicked = await pending;
    await new Promise((resolve) => setImmediate(resolve));
    pass(clicked, (r) => {
      assert.equal(r.record.http_status, 200);
      assert.doesNotMatch(r.text, /generation is unavailable|configured decision service/i);
      if (
        /gaming|processor/i.test(r.record.input) &&
        genuine.product_id === "apple-iphone-15-black-256gb"
      ) {
        assert.match(r.text, /A16/i);
        assert.doesNotMatch(
          r.text,
          /processor[^.]*not specified|high contrast ratio|fast response time/i,
        );
      }
    });
    tree = inner.render(ChatbotPanel, props);
    await find(tree, (n) => n.type === "PromptInput").props.onSubmit({
      text: "What is its price?",
    });
    const manual = await pending;
    pass(manual, (r) => {
      grounded(r);
      assert.ok(
        r.text.includes(
          catalog.find((p) => p.id === genuine.product_id).price.toLocaleString("en-US"),
        ),
      );
    });
    report.popup_click_handler = {
      execution:
        "Actual Chatbot onSelect + ChatbotPanel useEffect/send + live API in Node hooks; not browser",
      question: genuine.payload.suggestions[0],
      product_id: genuine.product_id,
      manual_input_after_click: true,
    };
    save();
    for (const [text, expectedQuantity] of [
      ["Add this product to my cart", 1],
      ["Increase the quantity to two", 2],
      ["What is my current total?", 2],
      ["Remove this product from my cart", 0],
    ]) {
      tree = inner.render(ChatbotPanel, props);
      const before = JSON.parse(JSON.stringify(renderCart().items));
      await find(tree, (n) => n.type === "PromptInput").props.onSubmit({ text });
      const result = await pending;
      const current = renderCart();
      result.record.cart_execution = {
        before,
        after: JSON.parse(JSON.stringify(current.items)),
        subtotal: current.subtotal,
        total_items: current.totalItems,
        persisted: JSON.parse(storage.getItem(stateLib.CART_STORAGE_KEY)),
        handler: "Actual ChatbotPanel.send -> applyChatCartResponse -> CartProvider",
      };
      pass(result, (r) => {
        assert.equal(
          current.items.find((item) => item.product.id === genuine.product_id)?.quantity ?? 0,
          expectedQuantity,
        );
        assert.deepEqual(
          result.record.cart_execution.after,
          result.record.cart_execution.persisted,
        );
        if (text === "What is my current total?") {
          assert.equal(r.record.response_source, "cart_state");
          assert.ok(r.text.includes("₹" + current.subtotal.toLocaleString("en-IN")));
          assert.equal(r.record.timings.ollama_call_count, 0);
        }
      });
    }
  }
  report.summary = {
    pass: records.filter((r) => r.status === "PASS").length,
    fail: records.filter((r) => r.status === "FAIL").length,
    unreviewed: records.filter((r) => r.status === "UNREVIEWED").length,
  };
  save();
}
main().catch((error) => {
  report.runner_error = error.stack;
  save();
  console.error(error);
  process.exitCode = 1;
});
