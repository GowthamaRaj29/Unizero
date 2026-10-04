// Client for the ai-services FastAPI app (app.py, `uvicorn app:app --port 8000`).
// Separate from api.js on purpose: api.js talks to the backend team's
// service (auth, DB persistence, workflow CRUD — port 8000). This talks
// directly to the standalone AI service your team can already run.
//
// ai-services has no auth layer yet (see app.py's ingestion comment: "no
// auth/role check here yet"), so no Authorization header is sent here.
// Once the backend proxies these calls instead, this file gets deleted
// and callers switch back to api.js — keep that boundary clean.

// Default is "/ai-api" (same-origin, proxied by Vite — see vite.config.js)
// rather than "http://localhost:8000" directly, because ai-services has
// no CORS middleware and we're keeping ai-services unmodified. Override
// with VITE_AI_API_URL if you've set up CORS on ai-services yourself
// (e.g. in a deployed environment with a real reverse proxy in front).
const AI_API_BASE_URL = import.meta.env.VITE_AI_API_URL || "/ai-api";

const request = async (endpoint, options = {}) => {
  const headers = {
    ...(options.body instanceof FormData
      ? {}
      : { "Content-Type": "application/json" }),
    ...(options.headers || {}),
  };

  const response = await fetch(`${AI_API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  let data = null;

  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    // FastAPI's HTTPException body is {"detail": "..."} — mirrors api.js's
    // error handling so calling code doesn't need to branch by client.
    const message = data?.detail || data?.message || "Something went wrong";

    throw new Error(
      Array.isArray(message)
        ? message.map((item) => item.msg || JSON.stringify(item)).join(", ")
        : message
    );
  }

  return data;
};

const aiApi = (endpoint, options = {}) => request(endpoint, options);

aiApi.get = (endpoint, options = {}) =>
  request(endpoint, { ...options, method: "GET" });

aiApi.post = (endpoint, body, options = {}) =>
  request(endpoint, {
    ...options,
    method: "POST",
    body: body instanceof FormData ? body : JSON.stringify(body ?? {}),
  });

export default aiApi;
export { AI_API_BASE_URL };