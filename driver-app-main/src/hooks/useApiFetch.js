const API_BASE = import.meta.env.VITE_API_BASE ?? import.meta.env.VITE_API_BASE_URL ?? "";

function getApiKey() {
  try {
    const stored = localStorage.getItem("logisight_tenant");
    if (stored) {
      const parsed = JSON.parse(stored);
      return parsed.api_key || "";
    }
  } catch {}
  return "";
}

export async function apiFetch(path, options = {}) {
  const apiKey = getApiKey();
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(apiKey ? { "X-API-Key": apiKey } : {}),
      ...(options.headers ?? {}),
    },
    ...options,
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

export function useApiFetch() {
  return apiFetch;
}
