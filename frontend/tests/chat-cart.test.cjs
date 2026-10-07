const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");

const compiled = ts.transpileModule(
  fs.readFileSync(path.join(__dirname, "../src/lib/chat-cart.ts"), "utf8"),
  { compilerOptions: { module: ts.ModuleKind.CommonJS } },
).outputText;
const loaded = { exports: {} };
new Function("module", "exports", compiled)(loaded, loaded.exports);
const { applyChatCartResponse } = loaded.exports;
const product = { id: "apple-iphone-13", name: "Apple iPhone 13", price: 49900, inStock: true };

function fixture(quantity = 2) {
  let items = quantity ? [{ product, quantity }] : [];
  const calls = [];
  return {
    getItems: () => items,
    calls,
    addToCart: (p) => {
      calls.push("add");
      if (p.inStock === false) return false;
      const existing = items.find((item) => item.product.id === p.id);
      if (existing) existing.quantity++;
      else items.push({ product: p, quantity: 1 });
      return true;
    },
    removeFromCart: (id) => { calls.push("remove"); items = items.filter((item) => item.product.id !== id); },
    updateQuantity: (id, q) => { calls.push("update"); items = items.map((item) => item.product.id === id ? { ...item, quantity: q } : item); },
  };
}
function response(action, expected, quantity, id = product.id) {
  return `[[SHOPAI_CART_ACTION:${JSON.stringify({ action, product_id: id, expected_quantity: expected, quantity })}]]Server confirmation`;
}
const getProduct = async () => product;

test("remove executes the client removal and strips internal command", async () => {
  const cart = fixture();
  const reply = await applyChatCartResponse(response("remove", 2, 0), cart, getProduct);
  assert.deepEqual(cart.getItems(), []);
  assert.deepEqual(cart.calls, ["remove"]);
  assert.match(reply, /Removed \*\*Apple iPhone 13\*\*/);
  assert.equal(reply.includes("SHOPAI"), false);
});
test("increase executes updateQuantity with the resulting client quantity", async () => {
  const cart = fixture();
  const reply = await applyChatCartResponse(response("increase", 2, 3), cart, getProduct);
  assert.equal(cart.getItems()[0].quantity, 3);
  assert.match(reply, /to 3 in your cart/);
});
test("decrease executes updateQuantity", async () => {
  const cart = fixture();
  await applyChatCartResponse(response("decrease", 2, 1), cart, getProduct);
  assert.equal(cart.getItems()[0].quantity, 1);
});
test("decreasing the last item removes it", async () => {
  const cart = fixture(1);
  await applyChatCartResponse(response("decrease", 1, 0), cart, getProduct);
  assert.deepEqual(cart.getItems(), []);
  assert.deepEqual(cart.calls, ["remove"]);
});
test("missing cart item never changes the client cart", async () => {
  const cart = fixture();
  const reply = await applyChatCartResponse(response("remove", 2, 0, "not-in-cart"), cart, getProduct);
  assert.match(reply, /isn't in your cart/);
  assert.deepEqual(cart.calls, []);
});
test("stale server quantity never overwrites a newer client cart", async () => {
  const cart = fixture(4);
  const reply = await applyChatCartResponse(response("increase", 2, 3), cart, getProduct);
  assert.match(reply, /Your cart changed/);
  assert.equal(cart.getItems()[0].quantity, 4);
  assert.deepEqual(cart.calls, []);
});
test("invalid command cannot set an arbitrary quantity", async () => {
  const cart = fixture();
  const reply = await applyChatCartResponse(response("increase", 2, 999), cart, getProduct);
  assert.match(reply, /Couldn't update/);
  assert.equal(cart.getItems()[0].quantity, 2);
  assert.deepEqual(cart.calls, []);
});
test("existing add marker still adds the fetched real product", async () => {
  const cart = fixture(0);
  const reply = await applyChatCartResponse(`[[SHOPAI_ADD_TO_CART:${product.id}]]Added product.`, cart, getProduct);
  assert.equal(cart.getItems()[0].product.id, product.id);
  assert.equal(cart.getItems()[0].quantity, 1);
  assert.equal(reply, "Added product.");
});
test("failed product lookup never retains a false added confirmation", async () => {
  const cart = fixture(0);
  const reply = await applyChatCartResponse(`[[SHOPAI_ADD_TO_CART:${product.id}]]Added product.`, cart, async () => { throw Error("Network failed"); });
  assert.match(reply, /Couldn't add/);
  assert.equal(reply.includes("Added product"), false);
  assert.deepEqual(cart.getItems(), []);
});
test("out-of-stock addition cannot claim success", async () => {
  const cart = fixture(0);
  const reply = await applyChatCartResponse(`[[SHOPAI_ADD_TO_CART:${product.id}]]Added product.`, cart, async () => ({ ...product, inStock: false }));
  assert.match(reply, /out of stock/);
  assert.deepEqual(cart.getItems(), []);
});
test("details and general replies never mutate a cart", async () => {
  const cart = fixture();
  for (const reply of ["You're welcome!", "### Apple iPhone 13\nProduct details."]) {
    assert.equal(await applyChatCartResponse(reply, cart, getProduct), reply);
  }
  assert.deepEqual(cart.calls, []);
});
test("conflicting commands cannot execute two cart operations", async () => {
  const cart = fixture();
  const reply = await applyChatCartResponse(`[[SHOPAI_ADD_TO_CART:${product.id}]]` + response("remove", 2, 0), cart, getProduct);
  assert.match(reply, /Couldn't update/);
  assert.deepEqual(cart.calls, []);
});
