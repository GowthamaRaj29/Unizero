import api from "./api";

export async function getWorkflows(params = {}) {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (
      value !== undefined &&
      value !== null &&
      value !== ""
    ) {
      searchParams.append(key, value);
    }
  });

  const query = searchParams.toString();

  return api.get(
    `/workflows${query ? `?${query}` : ""}`
  );
}

export async function getWorkflow(id) {
  return api.get(`/workflows/${id}`);
}

export async function createWorkflow(payload) {
  return api.post("/workflows", payload);
}

export async function updateWorkflow(id, payload) {
  return api.put(`/workflows/${id}`, payload);
}

export async function deleteWorkflow(id) {
  return api.delete(`/workflows/${id}`);
}

export default {
  getWorkflows,
  getWorkflow,
  createWorkflow,
  updateWorkflow,
  deleteWorkflow,
};