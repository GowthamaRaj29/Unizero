import api from "./api";

export async function getDataSources(params = {}) {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.append(key, value);
    }
  });

  const query = searchParams.toString();

  return api.get(`/data-sources${query ? `?${query}` : ""}`);
}

export async function getDataSource(id) {
  return api.get(`/data-sources/${id}`);
}

export async function createDataSource(payload) {
  return api.post("/data-sources", payload);
}

export async function uploadDataSource(workflowId, file) {
  const formData = new FormData();
  formData.append("file", file);
  return api.post(
    `/data-sources/upload?workflow_id=${encodeURIComponent(workflowId)}`,
    formData
  );
}

export async function updateDataSource(id, payload) {
  return api.put(`/data-sources/${id}`, payload);
}

export async function deleteDataSource(id) {
  return api.delete(`/data-sources/${id}`);
}

export default {
  getDataSources,
  getDataSource,
  createDataSource,
  updateDataSource,
  deleteDataSource,
};