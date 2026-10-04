import api from "./api";

export async function analyzeWorkflow(workflowId, payload) {
  return api.post(`/ai/workflows/${workflowId}/analyze`, payload);
}

export async function listBackendBreaks(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, value);
    }
  });
  const query = search.toString();
  return api.get(`/breaks${query ? `?${query}` : ""}`);
}

export async function getBackendBreak(breakId) {
  return api.get(`/breaks/${encodeURIComponent(breakId)}`);
}

export async function startBackendInvestigation(breakId, notes = "") {
  return api.post(`/breaks/${encodeURIComponent(breakId)}/investigate`, { notes });
}

export async function submitBackendInvestigation(breakId, justification) {
  return api.post(`/breaks/${encodeURIComponent(breakId)}/submit`, { justification });
}
