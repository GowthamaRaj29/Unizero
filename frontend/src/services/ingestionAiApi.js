import aiApi from "./aiApi";

// Wraps ai-services' ingestion + human-review-gate endpoints
// (app.py: /ingestion/start, /ingestion/{id}, /ingestion/{id}/review).
//
export async function validateData(payload) {
  return aiApi.post("/validate", payload);
}

export async function mapFields(payload) {
  return aiApi.post("/map-fields", payload);
}

export async function explainBreak(payload) {
  return aiApi.post("/explain-break", payload);
}

export async function getAiHealth() {
  return aiApi.get("/health");
}

export async function startIngestion(params) {
  // params: { source?, file?, businessRulesPath?, outlierField?, outlierGroupBy?,
  //           keyFields?, sheetName?, jsonDataKey?, xmlRecordTag? }
  if (params.file) {
    const formData = new FormData();
    formData.append("source_file", params.file);
    if (params.businessRulesPath) {
      formData.append("business_rules_path", params.businessRulesPath);
    }
    return aiApi.post("/ingestion/upload", formData);
  }

  return aiApi.post("/ingestion/start", {
    source: params.source,
    sheet_name: params.sheetName ?? 0,
    json_data_key: params.jsonDataKey ?? null,
    xml_record_tag: params.xmlRecordTag ?? null,
    business_rules_path: params.businessRulesPath ?? null,
    outlier_field: params.outlierField ?? "Amount",
    outlier_group_by: params.outlierGroupBy ?? "Currency",
    key_fields: params.keyFields ?? null,
  });
}

export async function getIngestionSession(sessionId) {
  return aiApi.get(`/ingestion/${sessionId}`);
}

// action: "GO_AHEAD" | "CORRECT_DATA"
export async function submitIngestionReview(sessionId, {
  action,
  actor = "user",
  patches,
  replacementRecords,
} = {}) {
  return aiApi.post(`/ingestion/${sessionId}/review`, {
    action,
    actor,
    patches: patches ?? null,
    replacement_records: replacementRecords ?? null,
  });
}

export default {
  startIngestion,
  getIngestionSession,
  submitIngestionReview,
  validateData,
  mapFields,
  explainBreak,
  getAiHealth,
};