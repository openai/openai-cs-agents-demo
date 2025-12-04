// Fetch ChatKit thread state for the Agent panel
export async function fetchThreadState(threadId: string) {
  try {
    const res = await fetch(`/chatkit/state?thread_id=${encodeURIComponent(threadId)}`);
    if (!res.ok) throw new Error(`State API error: ${res.status}`);
    return res.json();
  } catch (err) {
    console.error("Error fetching thread state:", err);
    return null;
  }
}

export async function fetchBootstrapState() {
  try {
    const res = await fetch(`/chatkit/bootstrap`);
    if (!res.ok) throw new Error(`Bootstrap API error: ${res.status}`);
    return res.json();
  } catch (err) {
    console.error("Error bootstrapping state:", err);
    return null;
  }
}
