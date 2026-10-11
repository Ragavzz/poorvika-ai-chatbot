// Explicitly invoked live checker; not part of the isolated *.test.cjs suite.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const root = path.resolve(__dirname, '../..');
function load(file) {
  const module = { exports: {} };
  new Function('module', 'exports', ts.transpileModule(fs.readFileSync(path.join(root, 'frontend/src/lib', file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText)(module, module.exports);
  return module.exports;
}
const { applyChatCartResponse } = load('chat-cart.ts');
const { setCartQuantity, cartTotals } = load('cart-state.ts');
const results = [];
const api = 'http://127.0.0.1:8000';
const log = fs.readdirSync(root).filter(name => /^lowram-backend-.*\.stderr\.log$/.test(name)).sort().at(-1);
const logOffset = fs.readFileSync(path.join(root, log), 'utf8').length;
async function getProduct(id) {
  const response = await fetch(`${api}/api/products/${encodeURIComponent(id)}`);
  assert.equal(response.status, 200);
  return response.json();
}
async function ask(message, session, cart = [], extra = {}, expectedStatus = 200) {
  const response = await fetch(api + '/api/chat', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: message + '\n\n<shopai_client_context>' +
      JSON.stringify({ session_id: session, cart: cart.map(({ product, quantity }) => ({ id: product.id, name: product.name, price: product.price, quantity })), ...extra }) + '</shopai_client_context>' }),
  });
  assert.equal(response.status, expectedStatus);
  const payload = await response.json();
  const text = payload.response ?? payload.detail;
  const ids = text.match(/\[\[SHOPAI_PRODUCTS:([^\]]*)\]\]/)?.[1].split(',').filter(Boolean) ?? [];
  results.push({ message, response: text, http_status: response.status, response_source: payload.response_source, product_ids: ids });
  return { text, ids };
}
async function main() {
  const health = await (await fetch(api + '/api/health')).json();
  assert.equal(health.decision_provider, 'rules');
  assert.equal(health.ollama_enabled, false);
  assert.equal(health.database.type, 'PostgreSQL');
  assert.equal(health.database.connected, true);
  const stamp = Date.now();
  const sid = label => `bugfix-${label}-${stamp}`;
  await ask('Show laptops under 100000', sid('hp'));
  const hp = await ask('Only HP laptops', sid('hp'));
  assert.ok(hp.ids.length >= 2);
  const hpRows = await Promise.all(hp.ids.map(getProduct));
  assert.ok(hpRows.every(p => p.brand === 'HP' && p.price <= 100000));
  const comparison = await ask('Compare the first two products', sid('hp'));
  assert.ok(hpRows.slice(0, 2).every(p => comparison.text.includes(p.name)));
  assert.ok(comparison.text.includes('| Price |') && comparison.text.includes('| Stock |'));
  await ask('Show products', sid('best'));
  assert.ok((await ask('Which one has the best specifications?', sid('best'))).text.includes('Which specification'));
  const phones = await ask('Show Samsung phones under 25000', sid('phones'));
  assert.ok(phones.ids.length >= 2);
  const phoneComparison = await ask('Compare the first two products', sid('phones'));
  const firstTwo = await Promise.all(phones.ids.slice(0, 2).map(getProduct));
  assert.ok(firstTwo.every(p => phoneComparison.text.includes(p.name)));
  let cheaper = await ask('Which one is cheaper?', sid('phones'));
  const phoneRows = await Promise.all(phones.ids.map(getProduct));
  const minimum = Math.min(...phoneRows.map(p => p.price));
  if (cheaper.ids.length === 0) {
    assert.ok(cheaper.text.includes('choose') && cheaper.text.includes(phoneRows.find(p => p.price === minimum).name));
    const index = phoneRows.findIndex(p => p.price === minimum);
    cheaper = await ask(`Tell me about the ${['first', 'second', 'third', 'fourth', 'fifth'][index]} product`, sid('phones'));
  }
  assert.equal(cheaper.ids.length, 1);
  const selected = await getProduct(cheaper.ids[0]);
  assert.equal(selected.price, minimum);
  assert.ok((await ask('Tell me more about that product.', sid('phones'))).text.includes(selected.name));
  assert.ok((await ask('What is its price?', sid('phones'))).text.includes(selected.price.toLocaleString('en-US')));
  let items = [];
  const cart = {
    getItems: () => items,
    addToCart: p => { items = [{ product: p, quantity: 1 }]; return true; },
    removeFromCart: id => { items = items.filter(item => String(item.product.id) !== String(id)); },
    updateQuantity: (id, q, fresh) => { items = setCartQuantity(items, id, q, fresh); },
  };
  async function verifyTotals() {
    const { subtotal, totalItems } = cartTotals(items);
    const expectedAmount = '₹' + subtotal.toLocaleString('en-IN', { maximumFractionDigits: 2 });
    for (const question of ['What is my current total?', 'What is the total price of all items?', 'How much is my cart?', 'What is my updated total?', 'How much do I owe?']) {
      const summary = await ask(question, sid('cart'), items);
      assert.ok(summary.text.includes(expectedAmount) && summary.text.includes(`for ${totalItems} item`));
      assert.ok(!summary.text.includes('disabled') && !summary.text.includes('SHOPAI_CART_ACTION'));
    }
  }
  await verifyTotals();
  const added = await ask('Add it to my cart', sid('cart'), items, { suggestion_product_id: selected.id, recent_product_ids: [selected.id] });
  await applyChatCartResponse(added.text, cart, getProduct);
  assert.equal(items.length, 1);
  await verifyTotals();
  const increased = await ask('Increase the quantity to two.', sid('cart'), items);
  const confirmation = await applyChatCartResponse(increased.text, cart, getProduct);
  assert.ok(confirmation.includes('to 2'));
  assert.deepEqual(cartTotals(items), { totalItems: 2, subtotal: selected.price * 2 });
  await verifyTotals();
  const viewed = await ask('Show me my cart.', sid('cart'), items);
  assert.ok(viewed.text.includes(selected.name) && viewed.text.includes('Qty: 2'));
  assert.ok(viewed.text.includes((selected.price * 2).toLocaleString('en-US')));
  const rejected = await ask(`Increase the quantity to ${selected.stock + 1}`, sid('cart'), items);
  assert.ok(!rejected.text.includes('SHOPAI_CART_ACTION'));
  const decreased = await ask('Decrease the quantity', sid('cart'), items);
  await applyChatCartResponse(decreased.text, cart, getProduct);
  assert.equal(items[0].quantity, 1);
  await verifyTotals();
  const removed = await ask('Remove that product from my cart.', sid('cart'), items);
  await applyChatCartResponse(removed.text, cart, getProduct);
  assert.equal(items.length, 0);
  await verifyTotals();
  assert.ok((await ask('Show me my cart.', sid('cart'), items)).text.includes('empty'));
  const multi = await ask('Show me mobiles and laptops under 100000', sid('multi'));
  assert.equal(new Set(multi.ids).size, multi.ids.length);
  const rows = await Promise.all(multi.ids.map(getProduct));
  assert.ok(rows.some(p => p.category === 'Mobiles') && rows.some(p => p.category === 'Computers'));
  assert.ok(rows.every(p => p.price <= 100000));
  const zero = await ask('Show Samsung phones under 1', sid('zero'));
  assert.ok(zero.text.includes("couldn't find") && !zero.text.includes('Active filters'));
  assert.ok(!(await ask('Why should I shop here?', sid('general'), [], {}, 503)).text.includes("couldn't find"));
  // Reconstructed client fixture using real catalog rows, not the user's browser cart.
  const iphone = await getProduct('apple-iphone-13-blue-128gb');
  const extras = await Promise.all([
    '2-5d-clear-tempered-glass-screen-protector-for-apple-ipad-air-4-10-9-inch',
    'sandisk-512gb-class-10-a1-microsd-without-adapter',
  ].map(getProduct));
  items = [{ product: iphone, quantity: 2 }, ...extras.map(product => ({ product, quantity: 1 }))];
  const quantityBefore = { items: JSON.parse(JSON.stringify(items)), totals: cartTotals(items) };
  assert.equal(quantityBefore.totals.totalItems, 4);
  const exactReduction = await ask('Reduce the iPhone 13 quantity to one', sid('iphone'), items);
  const reductionConfirmation = await applyChatCartResponse(exactReduction.text, cart, getProduct);
  assert.ok(reductionConfirmation.includes('to 1'));
  assert.equal(items.find(item => String(item.product.id) === String(iphone.id)).quantity, 1);
  const quantityAfter = { items: JSON.parse(JSON.stringify(items)), totals: cartTotals(items) };
  assert.equal(quantityAfter.totals.totalItems, 3);
  assert.equal(quantityBefore.totals.subtotal - quantityAfter.totals.subtotal, iphone.price);
  const updatedTotal = await ask('What is my current total?', sid('iphone'), items);
  assert.ok(updatedTotal.text.includes('₹' + quantityAfter.totals.subtotal.toLocaleString('en-IN')));
  items = [{ product: iphone, quantity: 4 }];
  for (const phrase of ['Reduce the iPhone 13 quantity to one', 'set iPhone 13 quantity to 1', 'decrease quantity to 1', 'change the quantity to one']) {
    items = [{ product: iphone, quantity: 4 }];
    const result = await ask(phrase, sid('iphone-forms'), items);
    await applyChatCartResponse(result.text, cart, getProduct);
    assert.equal(items[0].quantity, 1); // Absolute target, not a one-unit decrement.
  }
  const timings = fs.readFileSync(path.join(root, log), 'utf8').slice(logOffset).split('\n')
    .filter(line => line.includes('[TIMING] ')).map(line => JSON.parse(line.split('[TIMING] ')[1]));
  assert.equal(timings.length, results.length, 'unexpected concurrent requests; rerun on an idle session');
  results.forEach((result, index) => {
    const timing = timings[index];
    assert.equal(timing.decision_provider, 'rule-based');
    assert.equal(timing.laya_call_count, 0);
    assert.equal(timing.ollama_call_count, 0);
    if (timing.resolved_action === 'cart_action' || timing.resolved_action === 'comparison') assert.equal(timing.product_search_start, null);
    result.timings = timing;
  });
  const report = { result: 'PASS', health, frontend_http_status: (await fetch('http://127.0.0.1:8080')).status,
    checks: results, client_cart_execution: 'Actual frontend command handler and quantity/totals reducer, in a Node harness',
    exact_quantity_command: { before: quantityBefore, command_response: exactReduction.text, client_confirmation: reductionConfirmation, after: quantityAfter, updated_total: updatedTotal.text },
    rendered_browser_verification: 'Unavailable: no connected browser surface', backend_log: log };
  fs.writeFileSync(path.join(root, 'documentation', process.argv[2] || 'chat-bugfix-live-results.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ result: 'PASS', live_chat_requests: results.length, provider: health.decision_provider, product_count: health.database.product_count }));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
