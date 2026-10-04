import api from "./api";

export async function getIngestionSessions(params = {}) {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.append(key, value);
    }
  });

  const query = searchParams.toString();

  return api.get(
    `/ingestion/sessions${query ? `?${query}` : ""}`
  );
}

export async function getIngestionSession(id) {
  return api.get(`/ingestion/sessions/${id}`);
}

export async function startIngestion(dataSourceId) {
  return api.post("/ingestion/start", {
    data_source_id: dataSourceId,
  });
}

export async function validateIngestion(id) {
  return api.post(`/ingestion/${id}/validate`, {});
}

export async function approveIngestion(id) {
  return api.post(`/ingestion/${id}/approve`, {});
}

export async function retryIngestion(id) {
  return api.post(`/ingestion/${id}/retry`, {});
}

export default {
  getIngestionSessions,
  getIngestionSession,
  startIngestion,
  validateIngestion,
  approveIngestion,
  retryIngestion,
};