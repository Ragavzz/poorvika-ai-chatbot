type Timing = Record<string, string | number>;
const records = new Map<string, Timing>();
export function beginSuggestionTiming(key: string, reset = false) {
  if (!reset && records.has(key)) return String(records.get(key)!.request_id);
  records.set(key, {
    request_id: crypto.randomUUID(),
    context_ready: new Date().toISOString(),
    context_ready_ms: performance.now(),
  });
  if (records.size > 128) records.delete(records.keys().next().value!);
  return String(records.get(key)!.request_id);
}
export function recordSuggestionTiming(key: string, event: string, backend?: Timing) {
  const record = records.get(key);
  if (!record) return;
  if (event === "frontend_request_started") {
    record.request_id = crypto.randomUUID();
    record["context_to_request_start_ms"] = performance.now() - Number(record.context_ready_ms);
  }
  Object.assign(record, backend, {
    [event]: new Date().toISOString(),
    [event + "_ms"]: performance.now(),
  });
  if (event === "frontend_received")
    record["frontend_round_trip_ms"] =
      Number(record["frontend_received_ms"]) - Number(record["frontend_request_started_ms"]);
  if (event === "visible") {
    record["context_to_visible_ms"] =
      Number(record["visible_ms"]) - Number(record["context_ready_ms"]);
  }
  console.info("[SUGGESTION TIMING]", JSON.stringify({ key, ...record, state: event }));
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent("shopai:suggestion-timing", { detail: { key, ...record, state: event } }),
    );
  }
  return String(record.request_id);
}
