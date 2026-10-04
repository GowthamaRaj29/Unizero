import aiApi from "./aiApi";

// Wraps ai-services' field_mapping manual-override endpoints
// (app.py: /field-mapping/manual/...). Every function's request/response
// shape matches the Pydantic models in app.py exactly — see that file if
// a field here looks unfamiliar.

// Loads an AI mapping run into a reviewable session. session_ids are
// ingestion session IDs from /ingestion/start — one per data source
// (e.g. [faSessionId, rrSessionId]).
export async function autoMapFields(payload) {
  return aiApi.post("/field-mapping/auto", payload);
}

export async function createMappingSession(sessionIds, options = {}) {
  return aiApi.post("/field-mapping/manual/session", {
    session_ids: sessionIds,
    actor: options.actor ?? "user",
    ...options,
  });
}

export async function getMappingSession(mappingSessionId) {
  return aiApi.get(`/field-mapping/manual/${mappingSessionId}`);
}

// Manually map (or re-map) one field. category is COMMON | POTENTIAL | UNCOMMON.
export async function overrideMapping(mappingSessionId, {
  source,
  field,
  matchedSource,
  matchedField,
  category = "COMMON",
  actor = "user",
  note,
}) {
  return aiApi.post(`/field-mapping/manual/${mappingSessionId}/override`, {
    source,
    field,
    matched_source: matchedSource,
    matched_field: matchedField,
    category,
    actor,
    note,
  });
}

// ACCEPT | REJECT | KEEP_POTENTIAL on an AI-suggested (still-pending) entry.
export async function decideMapping(mappingSessionId, {
  key,
  decision,
  matchedField,
  actor = "user",
  note,
}) {
  return aiApi.post(`/field-mapping/manual/${mappingSessionId}/decision`, {
    key,
    decision,
    matched_field: matchedField,
    actor,
    note,
  });
}

export async function resetMappingToAi(mappingSessionId, key, actor = "user") {
  return aiApi.post(`/field-mapping/manual/${mappingSessionId}/reset`, {
    key,
    actor,
  });
}

export async function undoLastMapping(mappingSessionId, actor = "user") {
  return aiApi.post(`/field-mapping/manual/${mappingSessionId}/undo`, { actor });
}

// Sample rows for a mapped (or candidate) field pair. Pass either `key`
// (an existing entry's key) or the explicit source/field/matchedSource/matchedField.
export async function previewMapping(mappingSessionId, params = {}) {
  return aiApi.post(`/field-mapping/manual/${mappingSessionId}/preview`, {
    key: params.key,
    source: params.source,
    field: params.field,
    matched_source: params.matchedSource,
    matched_field: params.matchedField,
    rows: params.rows ?? 5,
  });
}

export async function validateMappingSession(mappingSessionId) {
  return aiApi.get(`/field-mapping/manual/${mappingSessionId}/validation`);
}

export async function uploadMappingFile(mappingSessionId, {
  content,
  source,
  matchedSource,
  category = "COMMON",
  actor = "user",
}) {
  return aiApi.post(`/field-mapping/manual/${mappingSessionId}/mapping-file`, {
    content,
    source,
    matched_source: matchedSource,
    category,
    actor,
  });
}

export default {
  autoMapFields,
  createMappingSession,
  getMappingSession,
  overrideMapping,
  decideMapping,
  resetMappingToAi,
  undoLastMapping,
  previewMapping,
  validateMappingSession,
  uploadMappingFile,
};