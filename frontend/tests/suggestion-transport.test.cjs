const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");
const { QueryClient, QueryObserver } = require("@tanstack/react-query");

function load(api) {
  const events = [];
  const compiled = ts.transpileModule(
    fs.readFileSync(path.join(__dirname, "../src/lib/product-suggestions.ts"), "utf8"),
    {
      compilerOptions: { module: ts.ModuleKind.CommonJS },
    },
  ).outputText;
  const module = { exports: {} };
  new Function("require", "module", "exports", compiled)(
    (id) =>
      id.includes("suggestion-timing")
        ? {
            beginSuggestionTiming: () => "correlation-test",
            recordSuggestionTiming: (key, state, details) => {
              events.push({ key, state, details });
              return "correlation-test";
            },
          }
        : { api },
    module,
    module.exports,
  );
  return { ...module.exports, events };
}
const iphone = {
  id: "apple-iphone-15-black-256gb",
  name: "Apple iPhone 15 (Black,256GB)",
  price: 69900,
};
const questions = [
  "Is this phone suitable for travel?",
  "How does this compare for battery life?",
  "What alternatives suit my daily needs?",
];

test("empty or invalid product context never qualifies", () => {
  const f = load({});
  for (const product of [
    { name: "Phone" },
    { ...iphone, price: NaN },
    { ...iphone, name: " " },
    { ...iphone, id: "" },
  ]) {
    assert.equal(f.getProductSuggestionContext({}, product), null);
  }
});

test("bounded timeout aborts transport and reports timeout without suggestions", async () => {
  const f = load({
    getChatSuggestions: (product, timing, options) =>
      new Promise((resolve, reject) => {
        assert.equal(options.requestId, "correlation-test");
        options.signal.addEventListener("abort", () => reject(new Error("aborted")), {
          once: true,
        });
      }),
  });
  await assert.rejects(
    f.getProductSuggestions(f.getProductSuggestionContext({}, iphone), undefined, 15),
    /timed out/,
  );
  assert.ok(f.events.some((event) => event.state === "timeout"));
  assert.equal(
    f.events.some((event) => event.state === "success"),
    false,
  );
});

test("navigation cancellation reports cancelled and no successful result", async () => {
  const controller = new AbortController();
  const f = load({
    getChatSuggestions: (product, timing, options) =>
      new Promise((resolve, reject) => {
        options.signal.addEventListener("abort", () => reject(new Error("navigation")), {
          once: true,
        });
      }),
  });
  const pending = f.getProductSuggestions(
    f.getProductSuggestionContext({}, iphone),
    controller.signal,
  );
  controller.abort();
  await assert.rejects(pending, /navigation/);
  assert.ok(f.events.some((event) => event.state === "cancelled"));
});

test("actual query observer cancels abandoned context and deduplicates a slow request", async () => {
  const client = new QueryClient();
  let calls = 0,
    cancelled = 0,
    finish;
  const old = new QueryObserver(client, {
    queryKey: ["suggestions", iphone.id],
    retry: false,
    queryFn: ({ signal }) => {
      calls++;
      return new Promise((resolve, reject) => {
        finish = resolve;
        signal.addEventListener(
          "abort",
          () => {
            cancelled++;
            reject(new Error("navigated"));
          },
          { once: true },
        );
      });
    },
  });
  const unsubscribe = old.subscribe(() => {});
  const duplicate = new QueryObserver(client, old.options);
  const unsubscribeDuplicate = duplicate.subscribe(() => {});
  assert.equal(calls, 1);
  unsubscribe();
  unsubscribeDuplicate();
  assert.equal(cancelled, 1);
  const nextKey = ["suggestions", "watch-other"];
  await client.fetchQuery({ queryKey: nextKey, queryFn: async () => questions });
  finish(["stale phone output"]);
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(client.getQueryData(nextKey), questions);
  assert.equal(client.getQueryData(["suggestions", iphone.id]), undefined);
  client.clear();
});

test("invalid model output and connection failure have no fallback", async () => {
  for (const getChatSuggestions of [
    async () => ({ suggestions: [] }),
    async () => {
      throw Error("connection failed");
    },
  ]) {
    const f = load({ getChatSuggestions });
    await assert.rejects(f.getProductSuggestions(f.getProductSuggestionContext({}, iphone)));
    assert.equal(
      f.events.some((event) => event.state === "success"),
      false,
    );
  }
});
