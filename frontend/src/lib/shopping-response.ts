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
  if (
    /^(?:Traceback\b|(?:Runtime|Value|Type|HTTP)Error:)|\[AI FLOW\]|Active filters:/im.test(text)
  ) {
    throw new Error("Invalid response from chat service");
  }

  if (!text) throw new Error("Empty response from chat service");
  return text;
}
