const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000/api";

const request = async (endpoint, options = {}) => {
  const token = localStorage.getItem("access_token");

  const headers = {
    ...(options.body instanceof FormData
      ? {}
      : {
          "Content-Type": "application/json",
        }),
    ...(options.headers || {}),
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
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
    const message =
      data?.detail ||
      data?.message ||
      data?.error ||
      "Something went wrong";

    throw new Error(
      Array.isArray(message)
        ? message.map((item) => item.msg).join(", ")
        : message
    );
  }

  return data;
};

// `api` stays callable directly — api(endpoint, options) — for callers
// like authApi.js that already use it that way, but also exposes
// verb methods so callers like mappingApi.js / ingestionApi.js that
// use api.get(...) / api.post(...) work too.
const api = (endpoint, options = {}) => request(endpoint, options);

api.get = (endpoint, options = {}) =>
  request(endpoint, { ...options, method: "GET" });

api.post = (endpoint, body, options = {}) =>
  request(endpoint, {
    ...options,
    method: "POST",
    body: body instanceof FormData ? body : JSON.stringify(body ?? {}),
  });

api.put = (endpoint, body, options = {}) =>
  request(endpoint, {
    ...options,
    method: "PUT",
    body: body instanceof FormData ? body : JSON.stringify(body ?? {}),
  });

api.patch = (endpoint, body, options = {}) =>
  request(endpoint, {
    ...options,
    method: "PATCH",
    body: body instanceof FormData ? body : JSON.stringify(body ?? {}),
  });

api.delete = (endpoint, options = {}) =>
  request(endpoint, { ...options, method: "DELETE" });

export default api;
export { API_BASE_URL };