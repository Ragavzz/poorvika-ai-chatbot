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

const stateModule = { exports: {} };
new Function("module", "exports", ts.transpileModule(
  fs.readFileSync(path.join(__dirname, "../src/lib/cart-state.ts"), "utf8"),
  { compilerOptions: { module: ts.ModuleKind.CommonJS } },
).outputText)(stateModule, stateModule.exports);
const { setCartQuantity, cartTotals, saveCartItems, readCartItems } = stateModule.exports;

test("exact iPhone reduction command updates quantities, totals and persisted client state", async () => {
  const iphone = { id: 'apple-iphone-13-blue-128gb', name: 'Apple iPhone 13 (Blue, 128GB)', price: 49900, inStock: true, stock: 5 };
  let items = [{ product: iphone, quantity: 2 },
    { product: { id: 'other-a', name: 'Other A', price: 3499 }, quantity: 1 },
    { product: { id: 'other-b', name: 'Other B', price: 3999 }, quantity: 1 }];
  const storage = new Map();
  const persist = () => saveCartItems({ setItem: (key, value) => storage.set(key, value) }, items);
  const cart = {
    getItems: () => items,
    addToCart() { throw Error('Unexpected add'); },
    removeFromCart: id => { items = setCartQuantity(items, id, 0); persist(); },
    updateQuantity: (id, q, fresh) => { items = setCartQuantity(items, id, q, fresh); persist(); },
  };
  assert.deepEqual(cartTotals(items), { totalItems: 4, subtotal: 107298 });
  const marker = response('set_quantity', 2, 1, iphone.id);
  const reply = await applyChatCartResponse(marker, cart, async () => { throw Error('Decrease needs no model or stock fetch'); });
  assert.match(reply, /to 1 in your cart/);
  assert.equal(items[0].quantity, 1);
  assert.deepEqual(cartTotals(items), { totalItems: 3, subtotal: 57398 });
  const reloaded = readCartItems({ getItem: key => storage.get(key) ?? null });
  assert.equal(reloaded[0].product.id, iphone.id);
  assert.equal(reloaded[0].quantity, 1);
  assert.deepEqual(cartTotals(reloaded), { totalItems: 3, subtotal: 57398 });
});

test("add then set quantity to two recalculates subtotal and persists after reload", async () => {
  let items = [];
  const cart = {
    getItems: () => items,
    addToCart: product => { items = [{ product, quantity: 1 }]; return true; },
    updateQuantity: (id, quantity, fresh) => { items = setCartQuantity(items, id, quantity, fresh); },
    removeFromCart: id => { items = setCartQuantity(items, id, 0); },
  };
  await applyChatCartResponse(`[[SHOPAI_ADD_TO_CART:${product.id}]]`, cart, async () => ({ ...product, stock: 3 }));
  await applyChatCartResponse(response("set_quantity", 1, 2), cart, async () => ({ ...product, stock: 3 }));
  assert.deepEqual(cartTotals(cart.getItems()), { totalItems: 2, subtotal: 99800 });
  const storage = new Map();
  saveCartItems({ setItem: (key, value) => storage.set(key, value) }, cart.getItems());
  const reloaded = readCartItems({ getItem: (key) => storage.get(key) ?? null });
  assert.equal(reloaded[0].quantity, 2);
  assert.deepEqual(cartTotals(reloaded), { totalItems: 2, subtotal: 99800 });
  await applyChatCartResponse(response("remove", 2, 0), cart, getProduct);
  assert.deepEqual(cartTotals(cart.getItems()), { totalItems: 0, subtotal: 0 });
  saveCartItems({ setItem: (key, value) => storage.set(key, value) }, cart.getItems());
  assert.deepEqual(readCartItems({ getItem: key => storage.get(key) ?? null }), []);
});

test("absolute quantity respects fresh stock and rejects negative values", async () => {
  const cart = fixture(1);
  const reply = await applyChatCartResponse(response("set_quantity", 1, 4), cart, async () => ({ ...product, stock: 3 }));
  assert.match(reply, /Only 3/);
  assert.equal(cart.getItems()[0].quantity, 1);
  assert.deepEqual(cart.calls, []);
  assert.match(await applyChatCartResponse(response("set_quantity", 1, -1), cart, getProduct), /Couldn't update/);
});

test("fresh lookup failures and cart changes during verification never claim success", async () => {
  const cart = fixture(1);
  assert.match(await applyChatCartResponse(response("set_quantity", 1, 2), cart, async () => { throw Error("offline"); }), /Couldn't update/);
  assert.deepEqual(cart.calls, []);
  const reply = await applyChatCartResponse(response("set_quantity", 1, 2), cart, async () => {
    cart.getItems()[0].quantity = 3;
    return product;
  });
  assert.match(reply, /Your cart changed/);
  assert.deepEqual(cart.calls, []);
});

test("cart drawer quantity reducer enforces numeric stock limits", () => {
  const items = [{ product: { ...product, stock: 2 }, quantity: 1 }];
  assert.equal(setCartQuantity(items, product.id, 3), items);
  assert.equal(setCartQuantity(items, product.id, 2)[0].quantity, 2);
  assert.equal(setCartQuantity(items, product.id, 2, { ...product, stock: 1 }), items);
});

test("valid specification and general replies are not replaced by generic errors", () => {
  const formatting = { exports: {} };
  new Function("module", "exports", ts.transpileModule(
    fs.readFileSync(path.join(__dirname, "../src/lib/shopping-response.ts"), "utf8"),
    { compilerOptions: { module: ts.ModuleKind.CommonJS } },
  ).outputText)(formatting, formatting.exports);
  const text = "| Features | AI model support and API connectivity |";
  assert.equal(formatting.exports.formatShoppingResponse(text), text);
  assert.throws(() => formatting.exports.formatShoppingResponse("Traceback: internal failure"), /Invalid response/);
  assert.throws(() => formatting.exports.formatShoppingResponse(""), /Empty response/);
});

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
