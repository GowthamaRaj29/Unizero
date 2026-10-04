import api from "./api";

export async function getInvestigations(params = {}) {
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
    `/investigations${query ? `?${query}` : ""}`
  );
}

export async function getInvestigation(id) {
  return api.get(`/investigations/${id}`);
}

export async function createInvestigation(payload) {
  return api.post("/investigations", payload);
}

export async function updateInvestigation(
  id,
  payload
) {
  return api.put(`/investigations/${id}`, payload);
}

export async function uploadEvidence(
  investigationId,
  file
) {
  const formData = new FormData();

  formData.append("file", file);

  return api.post(
    `/investigations/${investigationId}/evidence`,
    formData
  );
}

export async function submitInvestigation(
  investigationId
) {
  return api.post(
    `/investigations/${investigationId}/submit`,
    {}
  );
}

export async function getEvidence(investigationId) {
  return api.get(`/investigations/${investigationId}/evidence`);
}