# Product suggestion diagnostics

Run python scripts/measure_suggestions.py http://127.0.0.1:8000 to send three fresh generation requests per product. This writes real HTTP round-trip, backend, Ollama and validation timestamps to suggestion-performance-results.json. The test harness bypasses frontend caches; application caching is unchanged.

Backend timing is in Server-Timing and X-ShopAI-Suggestion-Timing response headers and [SUGGESTION TIMING] logs. Durations use monotonic clocks; timestamp strings use UTC.

To enable browser diagnostics in the storefront tab console, execute:

    sessionStorage.setItem("shopai:suggestion-diagnostics", "1");

The popup records context availability at layout commit, request start, response receipt and visibility after two animation frames. It logs [SUGGESTION TIMING] and dispatches a shopai:suggestion-timing event. Cached paths have no API/LLM duration. No production cache bypass or extra requests were added.

Disable with sessionStorage.removeItem("shopai:suggestion-diagnostics").

Browser controls were unavailable during verification. Actual frontend and context-to-visible latency are NOT in the HTTP benchmark and must not be inferred from API times.

suggestion-click-results.json holds the real six-question responses. suggestion-click-flow.log records Laya choices, effective existing actions and Ollama calls. The component test checks one existing-send call, preserved product ID, and unchanged later manual-message behavior.
