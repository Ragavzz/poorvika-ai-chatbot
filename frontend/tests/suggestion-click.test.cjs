const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");

function harness() {
  const slots = [];
  let index = 0,
    effects = [];
  return {
    hooks: {
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
      useEffect: (fn) => {
        index++;
        effects.push(fn);
      },
      lazy: () => "panel",
      Suspense: "suspense",
    },
    render: (component, props) => {
      index = 0;
      effects = [];
      return component(props);
    },
    effects: () => effects,
  };
}
const jsx = { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) };
test("manual assistant toggle opens and retains the mounted chat panel", () => {
  const outer = harness();
  const { Chatbot } = load("Chatbot.tsx", {
    react: outer.hooks,
    "react/jsx-runtime": jsx,
    "./ProductSuggestionPopup": { ProductSuggestionPopup: "popup" },
  });
  let tree = outer.render(Chatbot);
  assert.equal(find(tree, item => item.type === "panel"), null);
  find(tree, item => item.props?.["aria-label"] === "Open shopping assistant").props.onClick();
  tree = outer.render(Chatbot);
  assert.equal(find(tree, item => item.type === "panel").props.open, true);
  find(tree, item => item.props?.["aria-label"] === "Close shopping assistant").props.onClick();
  tree = outer.render(Chatbot);
  assert.equal(find(tree, item => item.type === "panel").props.open, false);
});
function load(file, modules) {
  const output = ts.transpileModule(
    fs.readFileSync(path.join(__dirname, "../src/components/storefront", file), "utf8"),
    {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        jsx: ts.JsxEmit.ReactJSX,
        target: ts.ScriptTarget.ES2022,
      },
    },
  ).outputText;
  const loaded = { exports: {} };
  new Function("require", "module", "exports", output)(
    (id) => modules[id] || new Proxy({}, { get: (_, key) => String(key) }),
    loaded,
    loaded.exports,
  );
  return loaded.exports;
}
function find(tree, predicate) {
  if (!tree || typeof tree !== "object") return null;
  if (Array.isArray(tree)) {
    for (const child of tree) {
      const found = find(child, predicate);
      if (found) return found;
    }
    return null;
  }
  return predicate(tree) ? tree : find(tree.props?.children, predicate);
}
test("popup selection opens the original chatbot and submits once with product context", async () => {
  const question = "Is the 120Hz refresh rate suitable for gaming on the Tecno Spark Go 1?";
  const productId = "tecno-spark-go-1-glittery-white-64gb-4gb-ram";
  const outer = harness();
  const { Chatbot } = load("Chatbot.tsx", {
    react: outer.hooks,
    "react/jsx-runtime": jsx,
    "./ProductSuggestionPopup": { ProductSuggestionPopup: "popup" },
  });
  let tree = outer.render(Chatbot);
  find(tree, (item) => item.type === "popup").props.onSelect(question, productId);
  tree = outer.render(Chatbot);
  const props = find(tree, (item) => item.type === "panel").props;
  assert.equal(props.open, true);
  assert.equal(props.suggestionRequest.productId, productId);
  const inner = harness(),
    requests = [];
  const { ChatbotPanel } = load("ChatbotPanel.tsx", {
    react: inner.hooks,
    "react/jsx-runtime": jsx,
    "@/services/api": {
      api: {
        chat: async (text) => {
          requests.push(text);
          return "Model reply";
        },
      },
    },
    "@/context/CartContext": {
      useCart: () => ({ items: [], addToCart() {}, removeFromCart() {}, updateQuantity() {} }),
    },
    "@/lib/shopping-response": { formatShoppingResponse: (text) => text },
    "@/lib/chat-cart": { applyChatCartResponse: async (text) => text },
  });
  inner.render(ChatbotPanel, props);
  for (const effect of inner.effects()) {
    effect();
    effect();
  }
  await new Promise((resolve) => setImmediate(resolve));
  tree = inner.render(ChatbotPanel, props);
  for (const effect of inner.effects()) effect();
  assert.equal(requests.length, 1);
  assert.ok(find(tree, (item) => item.props?.children === question));
  const context = JSON.parse(
    requests[0].match(/<shopai_client_context>(.*?)<\/shopai_client_context>/)[1],
  );
  assert.equal(context.suggestion_product_id, productId);
  assert.deepEqual(context.recent_product_ids, [productId]);
  await find(tree, (item) => item.type === "PromptInput").props.onSubmit({
    text: "Manual message",
  });
  assert.equal(requests.length, 2);
  const manualContext = JSON.parse(
    requests[1].match(/<shopai_client_context>(.*?)<\/shopai_client_context>/)[1],
  );
  assert.equal(manualContext.suggestion_product_id, undefined);
  assert.deepEqual(manualContext.recent_product_ids, [productId]);
});

test("cart-total submissions send the latest client snapshot after cart changes", async () => {
  const inner = harness();
  const requests = [];
  let items = [];
  const product = { id: 'total-test-product', name: 'Current Product', price: 17250 };
  const { ChatbotPanel } = load('ChatbotPanel.tsx', {
    react: inner.hooks,
    'react/jsx-runtime': jsx,
    '@/services/api': { api: { chat: async text => { requests.push(text); return 'Cart summary'; } } },
    '@/context/CartContext': { useCart: () => ({ items, addToCart() {}, removeFromCart() {}, updateQuantity() {} }) },
    '@/lib/shopping-response': { formatShoppingResponse: text => text },
    '@/lib/chat-cart': { applyChatCartResponse: async text => text },
  });
  const props = { open: true, onClose() {} };
  const phrases = ['What is my current total?', 'What is the total price of all items?', 'How much is my cart?', 'What is my updated total?', 'How much do I owe?'];
  const quantities = [0, 1, 3, 2, 0];
  for (let i = 0; i < phrases.length; i++) {
    items = quantities[i] ? [{ product, quantity: quantities[i] }] : [];
    const tree = inner.render(ChatbotPanel, props);
    await find(tree, node => node.type === 'PromptInput').props.onSubmit({ text: phrases[i] });
    const context = JSON.parse(requests.at(-1).match(/<shopai_client_context>(.*?)<\/shopai_client_context>/)[1]);
    assert.deepEqual(context.cart, items.map(({ product, quantity }) => ({ id: product.id, name: product.name, price: product.price, quantity })));
  }
  assert.equal(new Set(requests.map(request => JSON.parse(request.match(/<shopai_client_context>(.*?)<\/shopai_client_context>/)[1]).session_id)).size, 1);
});


test("welcome survives reopen once; provider errors stay separate from assistant answers", async () => {
  const inner = harness();
  const { ChatbotPanel } = load("ChatbotPanel.tsx", {
    react: inner.hooks, "react/jsx-runtime": jsx,
    "@/services/api": { api: { chat: async () => { throw new Error("Provider disabled by configuration"); } } },
    "@/context/CartContext": { useCart: () => ({ items: [], addToCart() {}, removeFromCart() {}, updateQuantity() {} }) },
    "@/lib/shopping-response": { formatShoppingResponse: text => text },
    "@/lib/chat-cart": { applyChatCartResponse: async text => text },
  });
  const props = { open: true, onClose() {} };
  let tree = inner.render(ChatbotPanel, props);
  const welcome = find(tree, node => node.type === "MessageResponse").props.children;
  assert.match(welcome, /Hi! Welcome to Poorvika Shopping Assistant/);
  inner.render(ChatbotPanel, { ...props, open: false });
  tree = inner.render(ChatbotPanel, props);
  assert.equal(find(tree, node => node.type === "MessageResponse").props.children, welcome);
  assert.equal(find(tree, node => node.props?.children === "Apple accessories"), null);
  await find(tree, node => node.type === "PromptInput").props.onSubmit({ text: "hello" });
  tree = inner.render(ChatbotPanel, props);
  assert.equal(find(tree, node => node.props?.role === "status").props.children, "Provider disabled by configuration");
  assert.equal(find(tree, node => node.type === "MessageResponse").props.children, welcome);
});
