/** Presentation only: callers handle product/cart markers before formatting. */
export function formatShoppingResponse(response: string): string {
  const text = response
    .replace(/\r\n?/g, "\n")
    .replace(/(?:<br\s*\/?\s*>[ \t]*)+/gi, "\n")
    .replace(/^[ \t]+$/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  // Hide implementation diagnostics without removing legitimate product specs
  // such as model numbers, operating systems, or AI features.
  if (/\b(?:PostgreSQL|FastAPI|Ollama|LLM|backend|database|grounded|AI assistant|AI model|chatbot|API|tool call|system prompt|intent extraction|shopping agent)\b/i.test(text)) {
    return "Sorry, we couldn't complete your request. Please try again.";
  }

  return text || "Please try again so we can help with your shopping.";
}
