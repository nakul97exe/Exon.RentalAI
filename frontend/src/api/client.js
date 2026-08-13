const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

/** Parse a JSON response, turning FastAPI's `detail` into a thrown Error. */
async function unwrap(res) {
  let data = null;
  try {
    data = await res.json();
  } catch {
    // Non-JSON body (e.g. a proxy error page) — fall through to the status text.
  }

  if (!res.ok) {
    // fetch() only rejects on network failure, so 4xx/5xx must be checked here.
    throw new Error(data?.detail || `${res.status} ${res.statusText}`);
  }
  return data;
}

/**
 * Ask the agent a question, optionally in the context of a selected parcel.
 * Attributes are sent per request rather than stored server-side.
 */
export async function askQuestion({ question, apn = null, parcelAttributes = null }) {
  const res = await fetch(`${API_BASE}/api/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      apn,
      parcel_attributes: parcelAttributes,
    }),
  });

  return unwrap(res);
}

export async function uploadDocument(file) {
  const formData = new FormData();
  // The field name must match FastAPI's parameter name: `file`.
  formData.append("file", file);

  // No Content-Type header — the browser sets it with the multipart boundary.
  const res = await fetch(`${API_BASE}/api/upload_document`, {
    method: "POST",
    body: formData,
  });

  return unwrap(res);
}
