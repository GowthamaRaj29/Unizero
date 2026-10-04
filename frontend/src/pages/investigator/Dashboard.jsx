import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { startIngestion, submitIngestionReview } from "../../services/ingestionAiApi";
import { createMappingSession } from "../../services/fieldMappingAiApi";
import { analyzeWorkflow } from "../../services/backendBreaksApi";
import {
  createWorkflow,
  getWorkflows,
  updateWorkflow,
} from "../../services/workflowApi";
import {
  createDataSource,
  updateDataSource,
  uploadDataSource,
} from "../../services/dataSourceApi";

const LS_MAPPING_KEY = "onerecon.mapping.lastSession";

// Every extension ai-services/ingestion/ingest.py actually detects
// (see its docstring: extension first, then content-sniffing as a
// fallback). Keep this in sync with _EXTENSION_MAP in that file rather
// than guessing — .pdf is deliberately left out, ai-services has no PDF
// ingestion path.
const ACCEPTED_SOURCE_EXTENSIONS = ".csv,.xlsx,.xls,.json,.xml";

function StatusPill({ status }) {
  const styles = {
    idle: "border-[#153d30] bg-[#041710] text-[#729487]",
    ingesting: "border-[#66551f] bg-[#2d2610] text-[#f2c95c]",
    REVIEW_REQUIRED: "border-[#66551f] bg-[#2d2610] text-[#f2c95c]",
    CLEAN: "border-[#1d6048] bg-[#0b2a1e] text-[#28d995]",
    APPROVED: "border-[#1d6048] bg-[#0b2a1e] text-[#28d995]",
    FAILED: "border-[#5a2828] bg-[#321717] text-[#f07171]",
  };
  const label = {
    idle: "Not started",
    ingesting: "Ingesting…",
    REVIEW_REQUIRED: "Needs review",
    CLEAN: "Clean",
    APPROVED: "Approved",
    FAILED: "Failed",
  };
  return (
    <span className={`inline-flex rounded-lg border px-2.5 py-1 text-[10px] font-semibold ${styles[status] || styles.idle}`}>
      {label[status] || status}
    </span>
  );
}

function Dashboard() {
  const navigate = useNavigate();

  const [showCreate, setShowCreate] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [workflows, setWorkflows] = useState([]);
  const [workflowLoadError, setWorkflowLoadError] = useState("");
  const [workflowDraft, setWorkflowDraft] = useState(null);

  const [workflowName, setWorkflowName] = useState("");
  const [period, setPeriod] = useState("June 2026");
  const [numberOfSources, setNumberOfSources] = useState(2);

  // One row per source: { path, file, status, sessionId, error, issues }
  const [sourceRows, setSourceRows] = useState([]);
  // Left empty by default on purpose — ai-services throws an unhandled
  // error if this path doesn't resolve relative to wherever `uvicorn` was
  // started, so we never guess one. Fill it in only if you know the exact
  // correct relative (or absolute) path on that machine.
  const [businessRulesPath, setBusinessRulesPath] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [creatingWorkflow, setCreatingWorkflow] = useState(false);

  useEffect(() => {
    let active = true;

    getWorkflows()
      .then((items) => {
        if (active) setWorkflows(Array.isArray(items) ? items : []);
      })
      .catch((error) => {
        if (active) setWorkflowLoadError(error.message || "Unable to load workflows.");
      });

    return () => {
      active = false;
    };
  }, []);

  const handleCreateWorkflow = async () => {
    if (!workflowName.trim()) return alert("Workflow name is required.");
    if (!period.trim()) return alert("Period is required.");

    const sourceCount = Number(numberOfSources);
    if (sourceCount < 2 || sourceCount > 5) {
      return alert("Choose between 2 and 5 data sources.");
    }

    setCreatingWorkflow(true);
    setUploadError("");

    try {
      const workflow = await createWorkflow({
        name: workflowName.trim(),
        period: period.trim(),
        number_of_sources: sourceCount,
      });

      setWorkflowDraft({
        id: workflow.id,
        workflowName: workflow.name,
        period: workflow.period,
        numberOfSources: sourceCount,
      });
    } catch (err) {
      setWorkflowLoadError(err.message || "Unable to create workflow.");
      return;
    } finally {
      setCreatingWorkflow(false);
    }

    setShowCreate(false);
    setShowUpload(true);
    setSourceRows(
      Array.from({ length: sourceCount }, () => ({
        path: "",
        file: null,
        status: "idle",
        sessionId: null,
        error: "",
        issues: null,
      }))
    );
    setUploadError("");
  };

  const updateRow = (index, patch) => {
    setSourceRows((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  };

  const handleFilePick = (index, file) => {
    if (!file) return;
    updateRow(index, {
      file,
      path: sourceRows[index].path || file.name,
      status: "idle",
      error: "",
    });
  };

  async function ingestOneSource(index) {
    const row = sourceRows[index];
    if (!row.path.trim()) {
      updateRow(index, { error: "Enter a source path or URL." });
      return null;
    }
    updateRow(index, { status: "ingesting", error: "" });
    try {
      let dataSource = null;
      if (row.file) {
        dataSource = await uploadDataSource(workflowDraft.id, row.file);
      }

      const summary = await startIngestion({
        source: row.path.trim(),
        file: row.file,
        businessRulesPath: businessRulesPath.trim() || null,
      });

      if (!dataSource) {
        dataSource = await createDataSource({
          workflow_id: workflowDraft.id,
          name: row.path.trim(),
          filename: row.path.trim(),
          path: row.path.trim(),
        });
      }

      await updateDataSource(dataSource.id, {
        status: summary.status,
        ai_session_id: summary.session_id,
      });

      updateRow(index, {
        status: summary.status,
        sessionId: summary.session_id,
        issues: summary,
        error: summary.error || "",
      });
      return { ...summary, data_source_id: dataSource.id };
    } catch (err) {
      updateRow(index, { status: "FAILED", error: err.message || "Ingestion failed." });
      return null;
    }
  }

  async function handleGoAhead(index) {
    const row = sourceRows[index];
    if (!row.sessionId) return;
    updateRow(index, { status: "ingesting" });
    try {
      const summary = await submitIngestionReview(row.sessionId, { action: "GO_AHEAD" });
      updateRow(index, { status: summary.status, issues: summary });
    } catch (err) {
      updateRow(index, { status: "REVIEW_REQUIRED", error: err.message });
    }
  }

  async function handleUploadDocuments() {
    if (!workflowDraft) return;
    setUploadError("");
    setSubmitting(true);

    try {
      // Ingest every row that hasn't already succeeded (lets you retry
      // just the rows that failed or need a path fix, without re-running
      // the ones that already came back CLEAN). We track results in this
      // local array rather than re-reading `sourceRows` afterwards —
      // setState is async, so the component's state wouldn't reflect the
      // ingest calls made in this same pass yet.
      const results = sourceRows.map((row) => ({ ...row }));

      for (let i = 0; i < results.length; i++) {
        if (results[i].status === "CLEAN" || results[i].status === "APPROVED") continue;
        // eslint-disable-next-line no-await-in-loop
        const summary = await ingestOneSource(i);
        results[i] = summary
          ? { ...results[i], status: summary.status, sessionId: summary.session_id }
          : { ...results[i], status: "FAILED" };
      }

      const ready = results.every((r) => r.status === "CLEAN" || r.status === "APPROVED");
      if (!ready) {
        // Some row came back REVIEW_REQUIRED or FAILED — its panel now
        // shows why (updateRow already pushed that into state), so stop
        // here instead of silently pressing on.
        setSubmitting(false);
        return;
      }

      // All sources ingested cleanly — create the manual-mapping session
      // so the workflow lands directly in Field Mapping with real data.
      // NOTE: the mapping session (and Mapping.jsx today) only compares
      // two sources at a time. For workflowDraft.numberOfSources > 2,
      // only the first two ingested sessions are wired into mapping here
      // — extending Mapping.jsx to N panels is a separate follow-up.
      const sessionIds = results.map((r) => r.sessionId).filter(Boolean);
      let mappingSessionId = null;
      let breakCount = 0;
      if (sessionIds.length >= 2) {
        const mappingSession = await createMappingSession(sessionIds.slice(0, 2));
        mappingSessionId = mappingSession.mapping_session_id;
        const analysis = await analyzeWorkflow(workflowDraft.id, {
          mapping_session_id: mappingSessionId,
          key_field: "TransactionID",
          actor: "investigator",
        });
        breakCount = analysis.breaks_created || 0;
        localStorage.setItem(
          LS_MAPPING_KEY,
          JSON.stringify({
            sourceSessionId: sessionIds[0],
            targetSessionId: sessionIds[1],
            mappingSessionId,
          })
        );
      }

      await updateWorkflow(workflowDraft.id, { status: "READY" });
      const refreshedWorkflows = await getWorkflows();
      setWorkflows(Array.isArray(refreshedWorkflows) ? refreshedWorkflows : []);
      setWorkflowDraft(null);
      setShowUpload(false);
      setSourceRows([]);
      setWorkflowName("");
      setPeriod("June 2026");
      setNumberOfSources(2);
    } catch (err) {
      setUploadError(err.message || "Could not create the workflow.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="w-full max-w-[1500px] mx-auto text-white">
      {/* Header */}
      <div className="mb-8 rounded-2xl border border-[#153d30] bg-[#071b14] px-6 py-5">
        <div className="flex items-center justify-between">
          <div>
            <p className="mb-1 text-xs font-medium tracking-[0.2em] text-[#52786a]">INVESTIGATOR</p>
            <h1 className="text-2xl font-semibold text-white">Workflow Dashboard</h1>
            <p className="mt-1 text-sm text-[#729487]">Create and manage reconciliation workflows.</p>
          </div>
          <button
            type="button"
            onClick={() => setShowCreate(!showCreate)}
            className="flex items-center gap-2 rounded-xl border border-[#28d995] bg-[#28d995] px-5 py-3 text-sm font-semibold text-[#03130f] transition hover:bg-[#35dc96]"
          >
            <span className="text-lg leading-none">+</span>
            Create Workflow
          </button>
        </div>
      </div>

      {workflowLoadError && (
        <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {workflowLoadError}
        </div>
      )}

      {/* Create Workflow */}
      {showCreate && (
        <div className="mb-8 rounded-2xl border border-[#153d30] bg-[#071b14] p-6">
          <div className="mb-6">
            <p className="text-xs font-medium tracking-[0.18em] text-[#28d995]">WORKFLOW SETUP</p>
            <h2 className="mt-1 text-lg font-semibold text-white">Create Workflow</h2>
            <p className="mt-1 text-sm text-[#729487]">Define the reconciliation workflow before uploading data.</p>
          </div>

          <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
            <div>
              <label className="mb-2 block text-sm font-medium text-[#91aaa0]">Workflow Name</label>
              <input
                type="text"
                value={workflowName}
                onChange={(event) => setWorkflowName(event.target.value)}
                placeholder="FA-MA-Reconciliation"
                className="w-full rounded-xl border border-[#153d30] bg-[#041710] px-4 py-3 text-sm text-white outline-none placeholder:text-[#52786a] focus:border-[#28d995]"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-[#91aaa0]">Period</label>
              <select
                value={period}
                onChange={(event) => setPeriod(event.target.value)}
                className="w-full rounded-xl border border-[#153d30] bg-[#041710] px-4 py-3 text-sm text-white outline-none focus:border-[#28d995]"
              >
                <option>June 2026</option>
                <option>July 2026</option>
                <option>August 2026</option>
                <option>September 2026</option>
              </select>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-[#91aaa0]">Number of Sources</label>
              <input
                type="number"
                min="2"
                max="5"
                value={numberOfSources}
                onChange={(event) => setNumberOfSources(Math.max(2, Number(event.target.value)))}
                className="w-full rounded-xl border border-[#153d30] bg-[#041710] px-4 py-3 text-sm text-white outline-none focus:border-[#28d995]"
              />
              <p className="mt-2 text-xs text-[#52786a]">Minimum 2 data sources required</p>
            </div>
          </div>

          <div className="mt-6 flex items-center gap-3 border-t border-[#153d30] pt-5">
            <button
              type="button"
              onClick={handleCreateWorkflow}
              disabled={creatingWorkflow}
              className="rounded-xl border border-[#28d995] bg-[#28d995] px-5 py-2.5 text-sm font-semibold text-[#03130f] transition hover:bg-[#35dc96]"
            >
              {creatingWorkflow ? "Creating…" : "Create Workflow"}
            </button>
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="rounded-xl border border-[#153d30] bg-[#041710] px-5 py-2.5 text-sm font-medium text-[#91aaa0] transition hover:border-[#28d995] hover:text-white"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Upload / Ingest sources */}
      {showUpload && workflowDraft && (
        <div className="mb-8 rounded-2xl border border-[#164b38] bg-[#071b14] p-6 shadow-[0_0_32px_rgba(40,217,149,0.08)]">
          <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-medium tracking-[0.18em] text-[#28d995]">STEP 2 OF 2</p>
              <h2 className="mt-1 text-lg font-semibold text-white">Ingest source data</h2>
              <p className="mt-1 text-sm text-[#729487]">
                {workflowDraft.workflowName} · {workflowDraft.period} · {workflowDraft.numberOfSources} source documents
              </p>
              <p className="mt-2 max-w-xl text-xs leading-5 text-[#5f8275]">
                Pick a local CSV, XLS/XLSX, JSON or XML file, or enter a path or URL
                that the ai-services process can read. Formats are auto-detected.
              </p>
            </div>
            <span className="rounded-full border border-[#1d6048] bg-[#0b2a1e] px-3 py-1 text-xs font-semibold text-[#28d995]">
              Sources required: {workflowDraft.numberOfSources}
            </span>
          </div>

          {uploadError && (
            <div className="mb-5 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              {uploadError}
            </div>
          )}

          <div className="mb-5">
            <label className="mb-2 block text-xs font-medium text-[#91aaa0]">
              Business rules file (optional — must be a path ai-services can read from wherever it was started)
            </label>
            <input
              type="text"
              value={businessRulesPath}
              onChange={(e) => setBusinessRulesPath(e.target.value)}
              placeholder="Leave blank to skip rule-based validation"
              className="w-full rounded-xl border border-[#153d30] bg-[#041710] px-4 py-2.5 text-sm text-white outline-none placeholder:text-[#4e7064] focus:border-[#28d995]"
            />
          </div>

          <div className="flex flex-col gap-4">
            {sourceRows.map((row, index) => (
              <div key={index} className="rounded-2xl border border-[#153d30] bg-[#041710] p-5">
                <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                  <span className="text-sm font-semibold text-white">Source {index + 1}</span>
                  <StatusPill status={row.status} />
                </div>

                <div className="flex flex-col gap-3 md:flex-row md:items-center">
                  <input
                    type="text"
                    value={row.path}
                    onChange={(e) => updateRow(index, { path: e.target.value, status: "idle", error: "" })}
                    placeholder='Path or URL, or use Browse…'
                    className="flex-1 rounded-xl border border-[#153d30] bg-[#071b14] px-4 py-2.5 text-sm text-white outline-none placeholder:text-[#4e7064] focus:border-[#28d995]"
                  />

                  <label className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-[#164b38] bg-[#071b14] px-4 py-2.5 text-xs font-medium text-[#28d995] transition hover:border-[#28d995]">
                    Browse…
                    <input
                      type="file"
                      accept={ACCEPTED_SOURCE_EXTENSIONS}
                      onChange={(e) => handleFilePick(index, e.target.files?.[0] || null)}
                      className="sr-only"
                    />
                  </label>

                  <button
                    type="button"
                    onClick={() => ingestOneSource(index)}
                    disabled={row.status === "ingesting" || row.status === "CLEAN" || row.status === "APPROVED"}
                    className="rounded-xl border border-[#1e815b] bg-[#0b3021] px-4 py-2.5 text-xs font-semibold text-[#39df99] transition hover:bg-[#10432f] disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {row.status === "ingesting" ? "Ingesting…" : "Ingest"}
                  </button>
                </div>

                {row.file && (
                  <p className="mt-2 text-[10px] text-[#5f8275]">Picked locally: {row.file.name}</p>
                )}
                {row.error && <p className="mt-2 text-xs text-red-400">{row.error}</p>}

                {/* Human review gate — ai-services pauses here (REVIEW_REQUIRED)
                    until a human explicitly says GO_AHEAD; nothing here can
                    silently auto-approve, matching ai-services' own design. */}
                {row.status === "REVIEW_REQUIRED" && row.issues && (
                  <div className="mt-4 rounded-xl border border-[#66551f] bg-[#2d2610] p-4">
                    <p className="text-xs font-semibold text-[#f2c95c] mb-2">
                      AI review required before this source can be used
                    </p>
                    {row.issues.ai_assessment?.summary && (
                      <p className="text-xs text-[#e8d9a8] mb-2">{row.issues.ai_assessment.summary}</p>
                    )}
                    {row.issues.validation_report?.rule_violations?.length > 0 && (
                      <p className="text-xs text-[#e8d9a8]">
                        {row.issues.validation_report.rule_violations.length} rule violation(s) found.
                      </p>
                    )}
                    <button
                      type="button"
                      onClick={() => handleGoAhead(index)}
                      className="mt-3 rounded-lg border border-[#f2c95c] bg-[#3a2f10] px-4 py-2 text-xs font-semibold text-[#f2c95c] transition hover:bg-[#4a3c14]"
                    >
                      Go Ahead anyway
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="mt-6 flex items-center gap-3 border-t border-[#153d30] pt-5">
            <button
              type="button"
              onClick={handleUploadDocuments}
              disabled={submitting}
              className="rounded-xl border border-[#28d995] bg-[#28d995] px-5 py-2.5 text-sm font-semibold text-[#03130f] transition hover:bg-[#35dc96] disabled:opacity-50"
            >
              {submitting ? "Working…" : "Ingest & create workflow"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowUpload(false);
                setWorkflowDraft(null);
                setSourceRows([]);
                setUploadError("");
              }}
              className="rounded-xl border border-[#153d30] bg-[#041710] px-5 py-2.5 text-sm font-medium text-[#91aaa0] transition hover:border-[#28d995] hover:text-white"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Existing Workflows */}
      <section>
        <div className="mb-4">
          <p className="text-xs font-medium tracking-[0.18em] text-[#52786a]">RECONCILIATION</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Existing Workflows</h2>
        </div>

        <div className="overflow-hidden rounded-2xl border border-[#153d30] bg-[#071b14]">
          <div className="grid grid-cols-4 border-b border-[#153d30] bg-[#081f17] px-6 py-4 text-xs font-semibold uppercase tracking-wider text-[#729487]">
            <div>Name</div>
            <div>Status</div>
            <div>Last Run</div>
            <div>Action</div>
          </div>

          {workflows.map((workflow) => (
            <div key={workflow.id} className="grid grid-cols-4 items-center border-b border-[#153d30] px-6 py-5 last:border-b-0">
              <div className="font-medium text-white">{workflow.name}</div>
              <div>
                {workflow.status === "SUCCESS" && (
                  <span className="inline-flex rounded-lg border border-[#1d6048] bg-[#0b2a1e] px-3 py-1 text-xs font-semibold text-[#28d995]">SUCCESS</span>
                )}
                {workflow.status === "FAILED" && (
                  <span className="inline-flex rounded-lg border border-[#5a2828] bg-[#321717] px-3 py-1 text-xs font-semibold text-[#f07171]">FAILED</span>
                )}
                {workflow.status === "RUNNING" && (
                  <span className="inline-flex rounded-lg border border-[#66551f] bg-[#2d2610] px-3 py-1 text-xs font-semibold text-[#f2c95c]">RUNNING</span>
                )}
                {workflow.status === "READY" && (
                  <span className="inline-flex rounded-lg border border-[#164b38] bg-[#0a261b] px-3 py-1 text-xs font-semibold text-[#72a795]">READY</span>
                )}
              </div>
              <div className="text-sm text-[#91aaa0]">{workflow.lastRun}</div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => navigate("/investigator/breaks")}
                  className="rounded-lg border border-[#164b38] bg-[#041710] px-4 py-2 text-sm font-medium text-[#28d995] transition hover:border-[#28d995] hover:bg-[#0b2a1e]"
                >
                  Investigate
                </button>
                {workflow.mappingSessionId && (
                  <button
                    type="button"
                    onClick={() => {
                      localStorage.setItem(
                        LS_MAPPING_KEY,
                        JSON.stringify({
                          sourceSessionId: workflow.sessionIds[0],
                          targetSessionId: workflow.sessionIds[1],
                          mappingSessionId: workflow.mappingSessionId,
                        })
                      );
                      navigate("/investigator/mapping");
                    }}
                    className="rounded-lg border border-[#245a75] bg-[#0b2430] px-4 py-2 text-sm font-medium text-[#78c4ed] transition hover:bg-[#103444]"
                  >
                    Field Mapping
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Quick Actions */}
      <div className="mt-8 flex items-center gap-3 border-t border-[#153d30] pt-6">
        <button type="button" onClick={() => navigate("/investigator/breaks")} className="rounded-xl border border-[#153d30] bg-[#071b14] px-5 py-3 text-sm font-medium text-[#91aaa0] transition hover:border-[#28d995] hover:text-[#28d995]">
          Breaks
        </button>
        <button type="button" onClick={() => navigate("/investigator/evidence")} className="rounded-xl border border-[#153d30] bg-[#071b14] px-5 py-3 text-sm font-medium text-[#91aaa0] transition hover:border-[#28d995] hover:text-[#28d995]">
          Evidence
        </button>
        <button type="button" onClick={() => navigate("/investigator/mapping")} className="rounded-xl border border-[#153d30] bg-[#071b14] px-5 py-3 text-sm font-medium text-[#91aaa0] transition hover:border-[#28d995] hover:text-[#28d995]">
          Field Mapping
        </button>
      </div>
    </div>
  );
}

export default Dashboard;
