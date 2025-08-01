// Helper to call the server
export async function callChatAPI(message: string, conversationId: string) {
  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId, message }),
    });
    if (!res.ok) throw new Error(`Chat API error: ${res.status}`);
    return res.json();
  } catch (err) {
    console.error("Error sending message:", err);
    return null;
  }
}

// ----- Agents config CRUD -----
export async function fetchAgentsConfig() {
  const res = await fetch("/agents-config", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch agents config");
  return res.json();
}

export async function putAgentsConfig(config: any) {
  const res = await fetch("/agents-config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error("Failed to save agents config");
  return res.json();
}

export async function resetAgentsConfig() {
  const res = await fetch("/agents-config/reset", { method: "POST" });
  if (!res.ok) throw new Error("Failed to reset agents config");
  return res.json();
}

export async function fetchWhitelists() {
  const res = await fetch("/agents-config/whitelists", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch whitelists");
  return res.json();
}

export async function fetchEffectiveInstructions() {
  const res = await fetch("/agents-config/effective", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch effective instructions");
  return res.json();
}
