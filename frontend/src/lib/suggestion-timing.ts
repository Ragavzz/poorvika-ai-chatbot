// Opt-in diagnostics: sessionStorage.setItem("shopai:suggestion-diagnostics", "1").
// No cache bypass, UI changes, or requests are introduced by these measurements.
type Timing = Record<string, string | number>;
const records = new Map<string, Timing>();
function enabled() {
  try {
    return (
      typeof window !== "undefined" &&
      sessionStorage.getItem("shopai:suggestion-diagnostics") === "1"
    );
  } catch {
    return false;
  }
}
export function beginSuggestionTiming(key: string) {
  if (!enabled()) return;
  records.set(key, {
    context_ready: new Date().toISOString(),
    context_ready_ms: performance.now(),
  });
}
export function recordSuggestionTiming(key: string, event: string, backend?: Timing) {
  if (!enabled()) return;
  const record = records.get(key);
  if (!record) return;
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
    console.info("[SUGGESTION TIMING]", key, JSON.stringify(record));
    window.dispatchEvent(
      new CustomEvent("shopai:suggestion-timing", { detail: { key, ...record } }),
    );
  }
}
