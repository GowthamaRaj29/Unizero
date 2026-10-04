import { useState, useEffect, useCallback } from "react";
import {
  createMappingSession,
  getMappingSession,
  overrideMapping,
  undoLastMapping,
  previewMapping,
  resetMappingToAi,
  validateMappingSession,
} from "../../services/fieldMappingAiApi";

// ---------------------------------------------------------------------
// KNOWN GAP (flagged for the ai-services team, not silently worked around):
// The manual-mapping session only returns entries for fields the AI found
// a candidate match for (see field_mapping/manual_mapping.py's
// create_mapping_session — it loops over auto_result.mappings). Fields
// with zero match candidates never appear here at all, so this page
// currently can't show a true "Unmapped, no candidate found" row the way
// the original mock data did. Fixing that needs the session's field_index
// exposed via a new endpoint or field on session.to_dict().
// ---------------------------------------------------------------------

const LS_KEY = "onerecon.mapping.lastSession";

function styleFor(entry) {
  if (!entry) {
    return { border: "border-l-red-500", text: "text-red-400" };
  }
  if (entry.is_manual_override) {
    return { border: "border-l-[#62b7e8]", text: "text-[#78c4ed]" };
  }
  if (entry.category === "POTENTIAL") {
    return { border: "border-l-[#f2c95c]", text: "text-[#f2c95c]" };
  }
  if (entry.category === "UNCOMMON") {
    return { border: "border-l-red-500", text: "text-red-400" };
  }
  return { border: "border-l-[#35dc96]", text: "text-[#35dc96]" };
}

function statusLabel(entry) {
  if (entry.is_manual_override) return "Manual Override";
  if (entry.category === "POTENTIAL") return "Potential Match";
  if (entry.category === "UNCOMMON") return "Uncommon Field";
  return "AI Match";
}

function Mapping() {
  // ---- session picker (this page has no session context from routing
  // today — see the integration notes for why this exists) ----
  const [sourceSessionId, setSourceSessionId] = useState("");
  const [targetSessionId, setTargetSessionId] = useState("");
  const [mappingSessionId, setMappingSessionId] = useState("");

  const [session, setSession] = useState(null); // raw session.to_dict()
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [leftSearch, setLeftSearch] = useState("");
  const [rightSearch, setRightSearch] = useState("");
  const [selectedKey, setSelectedKey] = useState(null); // selected left entry's key
  const [selectedTargetField, setSelectedTargetField] = useState(null);

  const [preview, setPreview] = useState(false);
  const [previewData, setPreviewData] = useState({}); // key -> preview response
  const [previewLoading, setPreviewLoading] = useState(false);
  const [validationData, setValidationData] = useState(null);

  // Restore last-used IDs so you're not retyping them on every reload.
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(LS_KEY) || "{}");
      if (saved.sourceSessionId) setSourceSessionId(saved.sourceSessionId);
      if (saved.targetSessionId) setTargetSessionId(saved.targetSessionId);
      if (saved.mappingSessionId) setMappingSessionId(saved.mappingSessionId);
    } catch {
      // ignore malformed localStorage
    }
  }, []);

  const refreshSession = useCallback(async (id) => {
    if (!id) return;
    setLoading(true);
    setError("");
    try {
      const data = await getMappingSession(id);
      setSession(data);
    } catch (err) {
      setError(err.message || "Could not load mapping session.");
    } finally {
      setLoading(false);
    }
  }, []);

  // If we already have a mapping_session_id saved (from a previous visit),
  // load it straight away instead of forcing a re-create.
  useEffect(() => {
    if (mappingSessionId) refreshSession(mappingSessionId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sourceName = session ? Object.keys(session.sources)[0] : null;
  const targetName = session ? Object.keys(session.sources)[1] : null;

  const leftEntries = session
    ? session.entries.filter((e) => e.source === sourceName)
    : [];
  // Right-hand panel: dedupe by matched_field so each target field shows once.
  const rightFieldsMap = new Map();
  leftEntries.forEach((e) => {
    if (e.matched_field && !rightFieldsMap.has(e.matched_field)) {
      rightFieldsMap.set(e.matched_field, e);
    }
  });
  const rightEntries = Array.from(rightFieldsMap.values());

  const filteredLeft = leftEntries.filter((e) =>
    e.field.toLowerCase().includes(leftSearch.toLowerCase())
  );
  const filteredRight = rightEntries.filter((e) =>
    (e.matched_field || "").toLowerCase().includes(rightSearch.toLowerCase())
  );

  const mappedCount = leftEntries.filter((e) => e.matched_field).length;
  const manualCount = leftEntries.filter((e) => e.is_manual_override).length;

  // ---- actions ----

  async function handleLoadSession() {
    if (!sourceSessionId || !targetSessionId) {
      setError("Enter both ingestion session IDs first.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await createMappingSession([sourceSessionId, targetSessionId]);
      setSession(data);
      setMappingSessionId(data.mapping_session_id);
      localStorage.setItem(
        LS_KEY,
        JSON.stringify({
          sourceSessionId,
          targetSessionId,
          mappingSessionId: data.mapping_session_id,
        })
      );
    } catch (err) {
      setError(err.message || "Could not create mapping session.");
      localStorage.removeItem(LS_KEY);
      setMappingSessionId("");
      setSession(null);
    } finally {
      setLoading(false);
    }
  }

  async function createMapping() {
    if (!selectedKey || !selectedTargetField || !session) return;
    const entry = session.entries.find((e) => e.key === selectedKey);
    if (!entry) return;

    setLoading(true);
    setError("");
    try {
      await overrideMapping(mappingSessionId, {
        source: sourceName,
        field: entry.field,
        matchedSource: targetName,
        matchedField: selectedTargetField,
        category: "COMMON",
        actor: "user",
      });
      await refreshSession(mappingSessionId);
      setSelectedKey(null);
      setSelectedTargetField(null);
    } catch (err) {
      setError(err.message || "Could not save the mapping.");
    } finally {
      setLoading(false);
    }
  }

  async function undoMappings() {
    if (!mappingSessionId) return;
    setLoading(true);
    setError("");
    try {
      await undoLastMapping(mappingSessionId, "user");
      await refreshSession(mappingSessionId);
    } catch (err) {
      setError(err.message || "Nothing to undo.");
    } finally {
      setLoading(false);
    }
  }

  async function resetSelectedMapping() {
    if (!mappingSessionId || !selectedKey) return;
    setLoading(true);
    setError("");
    try {
      await resetMappingToAi(mappingSessionId, selectedKey, "user");
      await refreshSession(mappingSessionId);
      setSelectedKey(null);
      setSelectedTargetField(null);
    } catch (err) {
      setError(err.message || "Could not reset the mapping.");
    } finally {
      setLoading(false);
    }
  }

  async function validateSession() {
    if (!mappingSessionId) return;
    setLoading(true);
    setError("");
    try {
      const data = await validateMappingSession(mappingSessionId);
      setValidationData(data);
    } catch (err) {
      setError(err.message || "Could not validate the mapping session.");
    } finally {
      setLoading(false);
    }
  }

  async function togglePreview() {
    const next = !preview;
    setPreview(next);
    if (!next || !session) return;

    setPreviewLoading(true);
    try {
      const mappedEntries = leftEntries.filter((e) => e.matched_field);
      const results = await Promise.all(
        mappedEntries.map((e) =>
          previewMapping(mappingSessionId, { key: e.key, rows: 5 })
            .then((data) => [e.key, data])
            .catch(() => [e.key, null])
        )
      );
      setPreviewData(Object.fromEntries(results));
    } finally {
      setPreviewLoading(false);
    }
  }

  // ---- render ----

  return (
    <div className="w-full max-w-[1500px] mx-auto">
      <div className="mb-8">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-[0.18em] text-[#4c9278]">
              Investigator / Workspace
            </p>
            <h1 className="text-3xl font-bold tracking-tight text-white">Field Mapping</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[#729487]">
              Compare source and target fields, review AI-generated mappings, and
              manually override mappings when required.
            </p>
          </div>
          <div className="flex items-center gap-2 self-start rounded-full border border-[#185b42] bg-[#09271c] px-4 py-2">
            <span className="h-2 w-2 rounded-full bg-[#35dc96] shadow-[0_0_8px_#35dc96]" />
            <span className="text-xs font-medium text-[#35dc96]">AI Mapping Enabled</span>
          </div>
        </div>
      </div>

      {/* SESSION PICKER — this page has no route/session context yet, so
          feed it two ingestion session IDs from /ingestion/start */}
      <div className="mb-6 rounded-2xl border border-[#153d30] bg-[#071b14] p-5">
        <p className="text-[10px] uppercase tracking-[0.18em] text-[#4f806e] mb-3">
          Ingestion Sessions
        </p>
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <input
            value={sourceSessionId}
            onChange={(e) => setSourceSessionId(e.target.value)}
            placeholder="Source ingestion session ID (e.g. FA)"
            className="flex-1 rounded-xl border border-[#173f31] bg-[#041710] py-3 px-4 text-sm text-white placeholder-[#4e7064] outline-none focus:border-[#237b58]"
          />
          <input
            value={targetSessionId}
            onChange={(e) => setTargetSessionId(e.target.value)}
            placeholder="Target ingestion session ID (e.g. RR)"
            className="flex-1 rounded-xl border border-[#173f31] bg-[#041710] py-3 px-4 text-sm text-white placeholder-[#4e7064] outline-none focus:border-[#237b58]"
          />
          <button
            onClick={handleLoadSession}
            disabled={loading}
            className="rounded-xl border border-[#1e815b] bg-[#0b3021] px-5 py-3 text-xs font-semibold text-[#39df99] transition hover:bg-[#10432f] disabled:opacity-40"
          >
            {loading ? "Loading…" : "Load Mapping Session"}
          </button>
        </div>
        {mappingSessionId && (
          <p className="mt-3 text-[10px] text-[#54796b]">
            mapping_session_id: <span className="text-[#78c4ed]">{mappingSessionId}</span>
          </p>
        )}
        {error && <p className="mt-3 text-xs text-red-400">{error}</p>}
      </div>

      {!session ? (
        <div className="rounded-2xl border border-[#153d30] bg-[#071b14] p-10 text-center text-sm text-[#5f8275]">
          Load a mapping session to see field comparisons.
        </div>
      ) : (
        <>
          {/* SUMMARY */}
          <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
            <div className="rounded-2xl border border-[#153d30] bg-[#071b14] p-4">
              <p className="text-[10px] uppercase tracking-wider text-[#52786a]">Source Fields</p>
              <p className="mt-2 text-2xl font-bold text-white">{leftEntries.length}</p>
            </div>
            <div className="rounded-2xl border border-[#153d30] bg-[#071b14] p-4">
              <p className="text-[10px] uppercase tracking-wider text-[#52786a]">Target Fields</p>
              <p className="mt-2 text-2xl font-bold text-white">{rightEntries.length}</p>
            </div>
            <div className="rounded-2xl border border-[#153d30] bg-[#071b14] p-4">
              <p className="text-[10px] uppercase tracking-wider text-[#52786a]">Mapped</p>
              <p className="mt-2 text-2xl font-bold text-[#35dc96]">{mappedCount}</p>
            </div>
            <div className="rounded-2xl border border-[#153d30] bg-[#071b14] p-4">
              <p className="text-[10px] uppercase tracking-wider text-[#52786a]">Manual Overrides</p>
              <p className="mt-2 text-2xl font-bold text-[#78c4ed]">{manualCount}</p>
            </div>
          </div>

          {/* PANELS */}
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <section className="overflow-hidden rounded-2xl border border-[#153d30] bg-[#071b14]">
              <div className="border-b border-[#153d30] p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.18em] text-[#4f806e]">
                      Source Dataset
                    </p>
                    <h2 className="mt-1 text-lg font-semibold text-white">{sourceName}</h2>
                  </div>
                  <span className="rounded-lg border border-[#164b38] bg-[#0a261b] px-3 py-1.5 text-[10px] font-medium text-[#72a795]">
                    {leftEntries.length} FIELDS
                  </span>
                </div>
                <div className="relative mt-5">
                  <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#55796c]">⌕</span>
                  <input
                    value={leftSearch}
                    onChange={(e) => setLeftSearch(e.target.value)}
                    placeholder="Search source fields..."
                    className="w-full rounded-xl border border-[#173f31] bg-[#041710] py-3 pl-9 pr-4 text-sm text-white placeholder-[#4e7064] outline-none transition focus:border-[#237b58]"
                  />
                </div>
              </div>

              <div>
                {filteredLeft.length === 0 && (
                  <div className="px-5 py-10 text-center text-sm text-[#5f8275]">No fields found.</div>
                )}
                {filteredLeft.map((entry) => {
                  const style = styleFor(entry);
                  return (
                    <button
                      key={entry.key}
                      onClick={() => setSelectedKey(entry.key)}
                      className={`w-full border-b border-[#102e24] border-l-4 px-5 py-5 text-left transition ${style.border} ${
                        selectedKey === entry.key ? "bg-[#0d3023]" : "hover:bg-[#092219]"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-[#e3f3ed]">{entry.field}</p>
                          <p className="mt-1 text-[10px] uppercase tracking-wider text-[#55796c]">Source field</p>
                        </div>
                        {entry.is_amount_candidate && (
                          <span className="shrink-0 rounded-md border border-[#5c4a1a] bg-[#231d0a] px-2 py-1 text-[9px] font-medium text-[#f2c95c]">
                            AMOUNT
                          </span>
                        )}
                      </div>

                      <div className="mt-4 flex items-center justify-between border-t border-[#123327] pt-3">
                        <span className="text-[9px] uppercase tracking-wider text-[#4e7668]">AI / Manual Mapping</span>
                        {entry.matched_field ? (
                          <span className={`text-xs ${style.text}`}>{entry.matched_field}</span>
                        ) : (
                          <span className="text-xs text-red-400">Unmapped</span>
                        )}
                      </div>

                      <div className="mt-3 flex items-center justify-between">
                        <span className="text-[10px] text-[#54796b]">{statusLabel(entry)}</span>
                        <span className={`text-[10px] font-semibold ${style.text}`}>
                          {Math.round((entry.score || 0) * 100)}% confidence
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </section>

            <section className="overflow-hidden rounded-2xl border border-[#153d30] bg-[#071b14]">
              <div className="border-b border-[#153d30] p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.18em] text-[#4f806e]">
                      Target Dataset
                    </p>
                    <h2 className="mt-1 text-lg font-semibold text-white">{targetName}</h2>
                  </div>
                  <span className="rounded-lg border border-[#164b38] bg-[#0a261b] px-3 py-1.5 text-[10px] font-medium text-[#72a795]">
                    {rightEntries.length} FIELDS
                  </span>
                </div>
                <div className="relative mt-5">
                  <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#55796c]">⌕</span>
                  <input
                    value={rightSearch}
                    onChange={(e) => setRightSearch(e.target.value)}
                    placeholder="Search target fields..."
                    className="w-full rounded-xl border border-[#173f31] bg-[#041710] py-3 pl-9 pr-4 text-sm text-white placeholder-[#4e7064] outline-none transition focus:border-[#237b58]"
                  />
                </div>
              </div>

              <div>
                {filteredRight.length === 0 && (
                  <div className="px-5 py-10 text-center text-sm text-[#5f8275]">No fields found.</div>
                )}
                {filteredRight.map((entry) => (
                  <button
                    key={entry.matched_field}
                    onClick={() => setSelectedTargetField(entry.matched_field)}
                    className={`w-full border-b border-[#102e24] px-5 py-5 text-left transition ${
                      selectedTargetField === entry.matched_field ? "bg-[#0d3023]" : "hover:bg-[#092219]"
                    }`}
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-[#e3f3ed]">{entry.matched_field}</p>
                      <p className="mt-1 text-[10px] uppercase tracking-wider text-[#55796c]">Target field</p>
                    </div>
                    <div className="mt-4 flex items-center justify-between border-t border-[#123327] pt-3">
                      <span className="text-[9px] uppercase tracking-wider text-[#4e7668]">Mapped From</span>
                      <span className="text-xs text-[#35dc96]">{entry.field}</span>
                    </div>
                  </button>
                ))}
              </div>
            </section>
          </div>

          {/* CONTROLS */}
          <div className="mt-6 rounded-2xl border border-[#153d30] bg-[#071b14] p-5">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-[10px] uppercase tracking-[0.18em] text-[#4f806e]">Mapping Selection</p>
                <div className="mt-2 flex flex-wrap items-center gap-3 text-sm">
                  <span className={selectedKey ? "text-[#35dc96]" : "text-[#5f8275]"}>
                    {selectedKey
                      ? session.entries.find((e) => e.key === selectedKey)?.field
                      : "Select source field"}
                  </span>
                  <span className="text-[#36594b]">→</span>
                  <span className={selectedTargetField ? "text-[#35dc96]" : "text-[#5f8275]"}>
                    {selectedTargetField || "Select target field"}
                  </span>
                </div>
              </div>

              <div className="flex flex-wrap gap-3">
                <button
                  onClick={createMapping}
                  disabled={!selectedKey || !selectedTargetField || loading}
                  className="rounded-xl border border-[#1e815b] bg-[#0b3021] px-5 py-3 text-xs font-semibold text-[#39df99] transition hover:bg-[#10432f] disabled:cursor-not-allowed disabled:opacity-30"
                >
                  Map Fields
                </button>
                <button
                  onClick={undoMappings}
                  disabled={!session.can_undo || loading}
                  className="rounded-xl border border-[#29483d] bg-[#091c15] px-5 py-3 text-xs font-semibold text-[#8ba89e] transition hover:border-[#42675a] hover:text-white disabled:opacity-40"
                >
                  Undo Last Change
                </button>
                <button
                  onClick={resetSelectedMapping}
                  disabled={!selectedKey || loading}
                  className="rounded-xl border border-[#5a3b3b] bg-[#241313] px-5 py-3 text-xs font-semibold text-[#f2a0a0] transition hover:border-[#f07171] disabled:opacity-40"
                >
                  Reset Selected
                </button>
                <button
                  onClick={validateSession}
                  disabled={loading}
                  className="rounded-xl border border-[#245a75] bg-[#0b2430] px-5 py-3 text-xs font-semibold text-[#78c4ed] transition hover:bg-[#103444]"
                >
                  Validate
                </button>
                <button
                  onClick={togglePreview}
                  className="rounded-xl border border-[#245a75] bg-[#0b2430] px-5 py-3 text-xs font-semibold text-[#78c4ed] transition hover:bg-[#103444]"
                >
                  {preview ? "Hide Preview" : "Preview Mapping"}
                </button>
              </div>
            </div>
          </div>

          {/* LEGEND */}
          <div className="mt-6 rounded-2xl border border-[#153d30] bg-[#071b14] px-5 py-4">
            <div className="flex flex-wrap items-center gap-x-7 gap-y-3">
              <span className="text-[10px] uppercase tracking-wider text-[#52786a]">Mapping Status</span>
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-[#35dc96]" />
                <span className="text-xs text-[#77998d]">Common / High Confidence</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-[#f2c95c]" />
                <span className="text-xs text-[#77998d]">Potential Match</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-red-400" />
                <span className="text-xs text-[#77998d]">Uncommon / Unmatched</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-[#78c4ed]" />
                <span className="text-xs text-[#77998d]">Manual Override</span>
              </div>
            </div>
          </div>

          {validationData && (
            <section className="mt-6 rounded-2xl border border-[#245a75] bg-[#071b14]">
              <div className="border-b border-[#153d30] px-6 py-5">
                <p className="text-[10px] uppercase tracking-[0.18em] text-[#4f806e]">Validation</p>
                <h2 className="mt-1 text-lg font-semibold text-white">Mapping Session Validation</h2>
              </div>
              <div className="p-6">
                <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-[#8ba89e]">
                  {JSON.stringify(validationData, null, 2)}
                </pre>
              </div>
            </section>
          )}

          {/* PREVIEW — real sample rows from /field-mapping/manual/{id}/preview,
              not client-invented data */}
          {preview && (
            <section className="mt-6 overflow-hidden rounded-2xl border border-[#1b5941] bg-[#071b14]">
              <div className="flex items-center justify-between border-b border-[#153d30] px-6 py-5">
                <div>
                  <p className="text-[10px] uppercase tracking-[0.18em] text-[#4f806e]">Validation</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">Mapping Preview</h2>
                </div>
                <span className="rounded-full border border-[#185b42] bg-[#0b3021] px-3 py-1.5 text-[10px] font-semibold text-[#35dc96]">
                  {previewLoading ? "LOADING…" : "SAMPLE DATA"}
                </span>
              </div>

              <div>
                {leftEntries
                  .filter((e) => e.matched_field)
                  .map((entry) => {
                    const data = previewData[entry.key];
                    return (
                      <div key={entry.key} className="border-b border-[#102e24] px-6 py-5 last:border-0">
                        <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_60px_1fr] mb-3">
                          <div>
                            <p className="text-[9px] uppercase tracking-wider text-[#4e7668]">Source</p>
                            <p className="mt-1 text-sm font-medium text-white">{entry.field}</p>
                          </div>
                          <div className="flex items-center justify-start text-[#35dc96] md:justify-center">→</div>
                          <div>
                            <p className="text-[9px] uppercase tracking-wider text-[#4e7668]">Target</p>
                            <p className="mt-1 text-sm font-medium text-[#35dc96]">{entry.matched_field}</p>
                          </div>
                        </div>
                        {data ? (
                          <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_60px_1fr]">
                            <div className="flex flex-wrap gap-2">
                              {data.left.values.map((v, i) => (
                                <span key={i} className="rounded-md border border-[#173b2e] bg-[#041710] px-2 py-1 text-[10px] text-[#77998d]">
                                  {String(v)}
                                </span>
                              ))}
                            </div>
                            <div />
                            <div className="flex flex-wrap gap-2">
                              {data.right.values.map((v, i) => (
                                <span key={i} className="rounded-md border border-[#173b2e] bg-[#041710] px-2 py-1 text-[10px] text-[#77998d]">
                                  {String(v)}
                                </span>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <p className="text-xs text-[#5f8275]">
                            {previewLoading ? "Fetching sample rows…" : "No preview available."}
                          </p>
                        )}
                        {data?.warnings?.length > 0 && (
                          <p className="mt-2 text-[10px] text-[#f2c95c]">{data.warnings[0].message}</p>
                        )}
                      </div>
                    );
                  })}
              </div>

              <div className="border-t border-[#153d30] bg-[#061811] px-6 py-4">
                <div className="flex flex-col gap-3 text-xs sm:flex-row sm:items-center sm:justify-between">
                  <span className="text-[#6b8d80]">Review all mappings before proceeding with reconciliation.</span>
                  <span className="font-medium text-[#35dc96]">
                    {mappedCount} / {leftEntries.length} fields mapped
                  </span>
                </div>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

export default Mapping;
