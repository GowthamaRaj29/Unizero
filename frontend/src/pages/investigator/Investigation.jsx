import {
  AlertTriangle,
  CheckCircle2,
  LoaderCircle,
  MessageSquare,
  Send,
  Upload,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import PageHeader from "../../components/PageHeader";
import StatusBadge from "../../components/StatusBadge";
import {
  changeBreakStatus,
  getBreakLineage,
  runBreakRca,
} from "../../services/breaksAiApi";
import {
  getBackendBreak,
  startBackendInvestigation,
  submitBackendInvestigation,
} from "../../services/backendBreaksApi";

function normalizeBreak(data) {
  const sourceA = data?.source_a ?? data?.sourceA ?? {};
  const sourceB = data?.source_b ?? data?.sourceB ?? {};
  const presentIn = data?.present_in ?? data?.presentIn ?? [];
  const missingIn = data?.missing_in ?? data?.missingIn ?? [];
  const breakTypes = data?.break_types ?? data?.breakTypes ?? [];
  const records = data?.records ?? {};
  const presentRecord = records[presentIn[0]] ?? Object.values(records)[0] ?? {};
  const sourceLabel = (source) => String(source).split(/[\\/]/).pop() || source;
  const differences = data?.differences ?? [];

  return {
    id: data?.break_id ?? data?.id ?? "—",
    runId: data?.run_id ?? data?.runId ?? data?.reconciliation_run_id ?? "—",
    resultId: data?.result_id ?? data?.resultId ?? "—",
    reconciliationType:
      (data?.reconciliation_type ?? data?.reconciliationType ?? data?.type ?? breakTypes.join(", ")) || "—",
    key: data?.key ?? data?.reconciliation_key ?? data?.record_key ?? data?.break_key ?? "—",
    sourceAValue:
      data?.source_a_value ?? data?.sourceAValue ?? sourceA?.value ?? sourceA?.amount ?? presentRecord?.Amount ?? "—",
    sourceBValue:
      data?.source_b_value ?? data?.sourceBValue ?? sourceB?.value ?? sourceB?.amount ?? (missingIn.length ? "Record missing" : "—"),
    difference:
      data?.difference ?? data?.difference_value ?? data?.delta ?? differences.map((item) => item.field ?? item.type).filter(Boolean).join(", ") ?? breakTypes.join(", ") ?? "—",
    field: data?.field ?? data?.failed_field ?? data?.reconciliation_field ?? data?.key_field ?? "—",
    sourceALabel: sourceLabel(presentIn[0] ?? "Source A"),
    sourceBLabel: sourceLabel(missingIn[0] ?? "Source B"),
    status: String(data?.status ?? "open").toLowerCase(),
    raw: data,
  };
}

function extractRca(data) {
  const root =
    data?.root_cause ??
    data?.rootCause ??
    data?.explanation ??
    data?.message ??
    data?.result?.root_cause ??
    data?.result?.rootCause ??
    "";

  const confidence =
    data?.confidence ??
    data?.ai_confidence ??
    data?.result?.confidence ??
    data?.result?.ai_confidence ??
    null;

  return {
    text: root || "No AI root-cause explanation was returned.",
    confidence:
      typeof confidence === "number"
        ? confidence > 1
          ? confidence / 100
          : confidence
        : null,
    raw: data,
  };
}

function Investigation() {
  const { id } = useParams();
  const breakId = decodeURIComponent(id || "");

  const [selectedBreak, setSelectedBreak] = useState(null);
  const [lineage, setLineage] = useState(null);
  const [rca, setRca] = useState(null);
  const [rootCause, setRootCause] = useState("");
  const [notes, setNotes] = useState("");
  const [resolution, setResolution] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [rcaLoading, setRcaLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [statusLoading, setStatusLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadBreak() {
    if (!breakId) return;

    setLoading(true);
    setError("");

    try {
      const data = await getBackendBreak(breakId);
      const normalized = normalizeBreak(data);
      setSelectedBreak(normalized);
      setStatus(normalized.status);

      try {
        const lineageData = await getBreakLineage(breakId);
        setLineage(lineageData);
      } catch {
        // Lineage is supplemental; the break itself can still be investigated.
        setLineage(null);
      }
    } catch (err) {
      setError(err.message || "Unable to load this break.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadBreak();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [breakId]);

  async function handleRunRca() {
    setRcaLoading(true);
    setError("");

    try {
      const result = await runBreakRca(breakId, {});
      setRca(extractRca(result));

      const generated = extractRca(result);
      if (generated.text) setRootCause(generated.text);
    } catch (err) {
      setError(err.message || "Unable to run root-cause analysis.");
    } finally {
      setRcaLoading(false);
    }
  }

  async function handleStatusChange(nextStatus) {
    setStatus(nextStatus);
    setStatusLoading(true);
    setError("");

    try {
      if (nextStatus === "investigating") {
        await startBackendInvestigation(breakId);
      } else {
        await changeBreakStatus(breakId, { status: nextStatus });
      }
      await loadBreak();
    } catch (err) {
      setError(err.message || "Unable to change break status.");
      setStatus(selectedBreak?.status || "open");
    } finally {
      setStatusLoading(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();

    if (!rootCause.trim()) {
      setError("Enter or generate a root cause before submitting.");
      return;
    }

    setSubmitting(true);
    setError("");

    try {
      await submitBackendInvestigation(
        breakId,
        [rootCause.trim(), notes.trim(), resolution.trim()]
          .filter(Boolean)
          .join("\n\n")
      );

      await changeBreakStatus(breakId, {
        status: "submitted_for_approval",
      });

      await loadBreak();
      alert("Investigator cause submitted and break moved to approval.");
    } catch (err) {
      setError(err.message || "Unable to submit the investigation.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-[#729487]">
        <LoaderCircle className="mr-3 animate-spin" size={20} />
        Loading break…
      </div>
    );
  }

  if (!selectedBreak) {
    return (
      <div className="w-full max-w-[1500px] mx-auto">
        <PageHeader
          eyebrow="INVESTIGATION"
          title="Break not found"
          description="The AI service did not return a break for this ID."
        />
        {error && (
          <div className="rounded-2xl border border-red-500/20 bg-red-500/10 p-5 text-sm text-red-300">
            {error}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="w-full max-w-[1500px] mx-auto text-white">
      <PageHeader
        eyebrow="INVESTIGATION"
        title={`Break ${selectedBreak.id}`}
        description="Review the reconciliation break, run AI root-cause analysis, document the investigator finding, and submit it for approval."
        action={<StatusBadge status={status} />}
      />

      {error && (
        <div className="mb-6 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="space-y-6">
            <section className="rounded-2xl border border-[#153d30] bg-[#071b14]">
              <div className="flex items-center justify-between border-b border-[#153d30] px-6 py-5">
                <div>
                  <h2 className="text-base font-semibold text-white">Break Summary</h2>
                  <p className="mt-1 text-sm text-[#729487]">
                    Data returned by GET /breaks/{selectedBreak.id}.
                  </p>
                </div>
                <AlertTriangle size={20} className="text-[#f07171]" />
              </div>

              <div className="grid grid-cols-1 gap-px bg-[#153d30] sm:grid-cols-2 lg:grid-cols-3">
                {[
                  ["Break ID", selectedBreak.id],
                  ["Result ID", selectedBreak.resultId],
                  ["Run ID", selectedBreak.runId],
                  ["Type", selectedBreak.reconciliationType],
                  ["Reconciliation Key", selectedBreak.key],
                  ["Failed Field", selectedBreak.field],
                ].map(([label, value]) => (
                  <div key={label} className="bg-[#071b14] px-6 py-5">
                    <span className="block text-xs uppercase tracking-wider text-[#52786a]">
                      {label}
                    </span>
                    <strong className="mt-2 block text-sm text-white">
                      {String(value)}
                    </strong>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-2xl border border-[#153d30] bg-[#071b14]">
              <div className="border-b border-[#153d30] px-6 py-5">
                <h2 className="text-base font-semibold text-white">Source vs Target</h2>
                <p className="mt-1 text-sm text-[#729487]">
                  Values returned by the reconciliation break service.
                </p>
              </div>

              <div className="grid grid-cols-1 gap-4 p-6 md:grid-cols-[1fr_140px_1fr]">
                <div className="rounded-xl border border-[#153d30] bg-[#041710] p-5">
                  <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-[#52786a]">
                    {selectedBreak.sourceALabel}
                  </div>
                  <div className="text-2xl font-semibold text-white">
                    {String(selectedBreak.sourceAValue)}
                  </div>
                </div>

                <div className="flex flex-col items-center justify-center rounded-xl border border-[#5a2828] bg-[#321717] p-5 text-center">
                  <span className="text-xs font-semibold uppercase tracking-wider text-[#f07171]">
                    Difference
                  </span>
                  <strong className="mt-2 text-xl text-[#f07171]">
                    {String(selectedBreak.difference)}
                  </strong>
                </div>

                <div className="rounded-xl border border-[#153d30] bg-[#041710] p-5">
                  <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-[#52786a]">
                    {selectedBreak.sourceBLabel}
                  </div>
                  <div className="text-2xl font-semibold text-white">
                    {String(selectedBreak.sourceBValue)}
                  </div>
                </div>
              </div>
            </section>

            <section className="rounded-2xl border border-[#153d30] bg-[#071b14]">
              <div className="flex items-center justify-between border-b border-[#153d30] px-6 py-5">
                <div>
                  <h2 className="text-base font-semibold text-white">
                    AI Root-Cause Analysis
                  </h2>
                  <p className="mt-1 text-sm text-[#729487]">
                    Run POST /breaks/{selectedBreak.id}/rca and review the returned explanation.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={handleRunRca}
                  disabled={rcaLoading}
                  className="rounded-xl border border-[#1e815b] bg-[#0b3021] px-4 py-2.5 text-xs font-semibold text-[#39df99] disabled:opacity-50"
                >
                  {rcaLoading ? "Analyzing…" : "Run AI RCA"}
                </button>
              </div>

              <div className="p-6">
                {!rca ? (
                  <div className="rounded-xl border border-dashed border-[#164b38] bg-[#041710] p-6 text-sm text-[#5f8275]">
                    No RCA has been run for this investigation yet.
                  </div>
                ) : (
                  <div className="rounded-xl border border-[#164b38] bg-[#041710] p-5">
                    <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#28d995]">
                      AI-generated explanation
                    </div>
                    <p className="mt-3 text-sm leading-6 text-[#b0c3bc]">
                      {rca.text}
                    </p>
                    {rca.confidence !== null && (
                      <div className="mt-5 border-t border-[#153d30] pt-4 text-sm text-[#729487]">
                        Confidence:{" "}
                        <strong className="text-[#28d995]">
                          {Math.round(rca.confidence * 100)}%
                        </strong>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </section>

            <section className="rounded-2xl border border-[#153d30] bg-[#071b14]">
              <div className="border-b border-[#153d30] px-6 py-5">
                <h2 className="text-base font-semibold text-white">Investigator Finding</h2>
                <p className="mt-1 text-sm text-[#729487]">
                  The investigator can override or confirm the AI finding before approval.
                </p>
              </div>

              <div className="space-y-5 p-6">
                <div>
                  <label htmlFor="rootCause" className="mb-2 block text-sm font-medium text-[#91aaa0]">
                    Root Cause
                  </label>
                  <textarea
                    id="rootCause"
                    rows="4"
                    value={rootCause}
                    onChange={(event) => setRootCause(event.target.value)}
                    placeholder="Describe the confirmed root cause..."
                    className="w-full resize-none rounded-xl border border-[#153d30] bg-[#041710] px-4 py-3 text-sm leading-6 text-white outline-none placeholder:text-[#52786a] focus:border-[#28d995]"
                  />
                </div>

                <div>
                  <label htmlFor="notes" className="mb-2 block text-sm font-medium text-[#91aaa0]">
                    Investigation Notes
                  </label>
                  <textarea
                    id="notes"
                    rows="5"
                    value={notes}
                    onChange={(event) => setNotes(event.target.value)}
                    placeholder="Document your investigation steps and findings..."
                    className="w-full resize-none rounded-xl border border-[#153d30] bg-[#041710] px-4 py-3 text-sm leading-6 text-white outline-none placeholder:text-[#52786a] focus:border-[#28d995]"
                  />
                </div>

                <div>
                  <label htmlFor="resolution" className="mb-2 block text-sm font-medium text-[#91aaa0]">
                    Proposed Resolution
                  </label>
                  <textarea
                    id="resolution"
                    rows="4"
                    value={resolution}
                    onChange={(event) => setResolution(event.target.value)}
                    placeholder="Describe the proposed resolution..."
                    className="w-full resize-none rounded-xl border border-[#153d30] bg-[#041710] px-4 py-3 text-sm leading-6 text-white outline-none placeholder:text-[#52786a] focus:border-[#28d995]"
                  />
                </div>
              </div>
            </section>
          </div>

          <aside className="space-y-6">
            <section className="rounded-2xl border border-[#153d30] bg-[#071b14]">
              <div className="border-b border-[#153d30] px-6 py-5">
                <h2 className="text-base font-semibold text-white">Break Status</h2>
              </div>
              <div className="p-6">
                <select
                  value={status}
                  onChange={(event) => handleStatusChange(event.target.value)}
                  disabled={statusLoading}
                  className="w-full rounded-xl border border-[#153d30] bg-[#041710] px-4 py-3 text-sm text-white outline-none focus:border-[#28d995] disabled:opacity-50"
                >
                  <option value="open">Open</option>
                  <option value="investigating">Investigating</option>
                  <option value="submitted_for_approval">Pending Approval</option>
                  <option value="authorized">Authorized</option>
                  <option value="closed">Closed</option>
                </select>
                <p className="mt-3 text-xs text-[#52786a]">
                  Uses POST /breaks/{selectedBreak.id}/status.
                </p>
              </div>
            </section>

            <section className="rounded-2xl border border-[#153d30] bg-[#071b14]">
              <div className="border-b border-[#153d30] px-6 py-5">
                <h2 className="text-base font-semibold text-white">Lineage</h2>
                <p className="mt-1 text-sm text-[#729487]">
                  GET /breaks/{selectedBreak.id}/lineage
                </p>
              </div>
              <div className="max-h-64 overflow-auto p-6">
                {lineage ? (
                  <pre className="whitespace-pre-wrap break-words text-xs leading-5 text-[#8ba89e]">
                    {JSON.stringify(lineage, null, 2)}
                  </pre>
                ) : (
                  <p className="text-sm text-[#5f8275]">No lineage data returned.</p>
                )}
              </div>
            </section>

            <section className="rounded-2xl border border-[#153d30] bg-[#071b14]">
              <div className="border-b border-[#153d30] px-6 py-5">
                <h2 className="text-base font-semibold text-white">Evidence</h2>
                <p className="mt-1 text-sm text-[#729487]">
                  Evidence is stored by the backend and can be uploaded from the Evidence workspace.
                </p>
              </div>
              <div className="p-6">
                <div className="flex flex-col items-center rounded-xl border border-dashed border-[#164b38] bg-[#041710] px-5 py-7 text-center">
                  <Upload size={22} className="text-[#28d995]" />
                  <strong className="mt-3 text-sm text-white">Evidence workspace available</strong>
                  <span className="mt-2 text-xs leading-5 text-[#52786a]">
                    Select this investigation in the Evidence workspace to attach supporting files.
                  </span>
                </div>
              </div>
            </section>

            <section className="rounded-2xl border border-[#153d30] bg-[#071b14]">
              <div className="border-b border-[#153d30] px-6 py-5">
                <h2 className="text-base font-semibold text-white">Investigation Status</h2>
              </div>
              <div className="p-6">
                <div className="space-y-0">
                  <div className="relative flex gap-3 pb-7">
                    <div className="absolute left-[9px] top-6 h-[calc(100%-10px)] w-px bg-[#164b38]" />
                    <CheckCircle2 size={19} className="relative z-10 shrink-0 text-[#28d995]" />
                    <div>
                      <strong className="block text-sm text-white">Break detected</strong>
                      <span className="mt-1 block text-xs text-[#52786a]">Deterministic engine</span>
                    </div>
                  </div>
                  <div className="relative flex gap-3 pb-7">
                    <div className="absolute left-[9px] top-6 h-[calc(100%-10px)] w-px bg-[#164b38]" />
                    <MessageSquare size={19} className="relative z-10 shrink-0 text-[#28d995]" />
                    <div>
                      <strong className="block text-sm text-[#28d995]">Investigation</strong>
                      <span className="mt-1 block text-xs text-[#52786a]">Current step</span>
                    </div>
                  </div>
                  <div className="flex gap-3">
                    <Send size={19} className="shrink-0 text-[#52786a]" />
                    <div>
                      <strong className="block text-sm text-[#789b8e]">Approval</strong>
                      <span className="mt-1 block text-xs text-[#52786a]">Submit investigator cause to continue</span>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <button
              type="submit"
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-[#28d995] bg-[#28d995] px-5 py-3 text-sm font-semibold text-[#03130f] transition hover:bg-[#35dc96] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={submitting}
            >
              {submitting ? "Submitting…" : (
                <>
                  <Send size={17} />
                  Submit for Approval
                </>
              )}
            </button>
          </aside>
        </div>
      </form>
    </div>
  );
}

export default Investigation;
