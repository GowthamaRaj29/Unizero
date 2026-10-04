import aiApi from "./aiApi";

export async function analyzeBreaks(payload = {}) {
  return aiApi.post("/breaks/analyze", payload);
}

export async function listBreaks(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") search.set(key, value);
  });
  const query = search.toString();
  return aiApi.get(`/breaks${query ? `?${query}` : ""}`);
}

export async function getBreakSummary(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") search.set(key, value);
  });
  const query = search.toString();
  return aiApi.get(`/breaks/summary${query ? `?${query}` : ""}`);
}

export async function analyzeAggregates(payload = {}) {
  return aiApi.post("/breaks/aggregate/analyze", payload);
}

export async function getBreak(breakId) {
  return aiApi.get(`/breaks/${encodeURIComponent(breakId)}`);
}

export async function runBreakRca(breakId, payload = {}) {
  return aiApi.post(`/breaks/${encodeURIComponent(breakId)}/rca`, payload);
}

export async function changeBreakStatus(breakId, payload) {
  return aiApi.post(`/breaks/${encodeURIComponent(breakId)}/status`, payload);
}

export async function getBreakLineage(breakId) {
  return aiApi.get(`/breaks/${encodeURIComponent(breakId)}/lineage`);
}

export async function submitInvestigatorCause(breakId, payload) {
  return aiApi.post(`/breaks/${encodeURIComponent(breakId)}/investigator/cause`, payload);
}

export async function authorizeBreak(breakId, payload = {}) {
  return aiApi.post(`/breaks/${encodeURIComponent(breakId)}/authorize`, payload);
}

export async function bulkAuthorize(payload) {
  return aiApi.post("/breaks/authorize/bulk", payload);
}

export async function uploadApprovals(payload) {
  return aiApi.post("/breaks/authorize/upload", payload);
}

export default {
  analyzeBreaks,
  listBreaks,
  getBreakSummary,
  analyzeAggregates,
  getBreak,
  runBreakRca,
  changeBreakStatus,
  getBreakLineage,
  submitInvestigatorCause,
  authorizeBreak,
  bulkAuthorize,
  uploadApprovals,
};
