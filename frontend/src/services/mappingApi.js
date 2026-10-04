import api from "./api";

export async function getFieldMappings(workflowId) {
  const query = workflowId
    ? `?workflow_id=${encodeURIComponent(workflowId)}`
    : "";

  return api.get(`/field-mappings${query}`);
}

export async function getFieldMapping(id) {
  return api.get(`/field-mappings/${id}`);
}

export async function createFieldMapping(payload) {
  return api.post("/field-mappings", payload);
}

export async function updateFieldMapping(id, payload) {
  return api.put(`/field-mappings/${id}`, payload);
}

export async function deleteFieldMapping(id) {
  return api.delete(`/field-mappings/${id}`);
}

export async function uploadCrosswalk(workflowId, file) {
  const formData = new FormData();

  formData.append("workflow_id", workflowId);
  formData.append("file", file);

  return api.post("/crosswalks/upload", formData);
}

export async function getCrosswalks(workflowId) {
  const query = workflowId
    ? `?workflow_id=${encodeURIComponent(workflowId)}`
    : "";

  return api.get(`/crosswalks${query}`);
}

export async function addValueCrosswalk(fieldMappingId, payload) {
  return api.post(
    `/field-mappings/${fieldMappingId}/values`,
    payload
  );
}

export default {
  getFieldMappings,
  getFieldMapping,
  createFieldMapping,
  updateFieldMapping,
  deleteFieldMapping,
  uploadCrosswalk,
  getCrosswalks,
  addValueCrosswalk,
};