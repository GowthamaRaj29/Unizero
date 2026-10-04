import {
  ArrowRight,
  RefreshCw,
  Search,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useCallback, useEffect, useMemo, useState } from "react";
import PageHeader from "../../components/PageHeader";
import StatusBadge from "../../components/StatusBadge";
import { listBackendBreaks } from "../../services/backendBreaksApi";

function normalizeBreak(item, index) {
  const sourceA = item?.source_a ?? item?.sourceA ?? {};
  const sourceB = item?.source_b ?? item?.sourceB ?? {};
  const presentIn = item?.present_in ?? item?.presentIn ?? [];
  const missingIn = item?.missing_in ?? item?.missingIn ?? [];
  const breakTypes = item?.break_types ?? item?.breakTypes ?? [];
  const priority = item?.priority ?? {};
  const shortSource = (source) => String(source).split(/[\\/]/).pop() || source;

  return {
    id: item?.break_id ?? item?.id ?? `BREAK-${index + 1}`,
    displayId: String(item?.break_id ?? item?.id ?? `BREAK-${index + 1}`).slice(0, 8),
    runId: item?.run_id ?? item?.runId ?? item?.reconciliation_run_id ?? "—",
    reconciliationType:
      (item?.reconciliation_type ?? item?.reconciliationType ?? item?.type ?? breakTypes.join(", ")) || "—",
    key: item?.key ?? item?.reconciliation_key ?? item?.record_key ?? item?.break_key ?? "—",
    sourceAValue:
      item?.source_a_value ??
      item?.sourceAValue ??
      sourceA?.value ?? sourceA?.amount ?? shortSource(presentIn[0] ?? "—"),
    sourceBValue:
      item?.source_b_value ??
      item?.sourceBValue ??
      sourceB?.value ?? sourceB?.amount ?? shortSource(missingIn[0] ?? "—"),
    difference:
      item?.difference ??
      item?.difference_value ??
      item?.delta ??
      (breakTypes.join(", ") || "—"),
    status: String(item?.status ?? "OPEN").toLowerCase(),
    priority: priority.band ?? "—",
    raw: item,
  };
}

function extractBreakList(data) {
  if (Array.isArray(data)) return data;
  return data?.breaks ?? data?.items ?? data?.results ?? data?.data ?? [];
}

function extractSummary(data) {
  if (!data || typeof data !== "object") return {};
  const byStatus = data.by_status ?? data.byStatus ?? {};
  return {
    total: data.total ?? data.total_breaks ?? data.count ?? 0,
    open: data.open ?? data.open_breaks ?? byStatus.OPEN ?? byStatus.open ?? 0,
    investigating:
      data.investigating ?? data.investigating_breaks ?? byStatus.INVESTIGATING ?? byStatus.investigating ?? 0,
    pending:
      data.submitted_for_approval ??
      data.pending_approval ??
      data.pending ?? byStatus.SUBMITTED_FOR_APPROVAL ?? byStatus.submitted_for_approval ?? 0,
  };
}

function Breaks() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [breaks, setBreaks] = useState([]);
  const [summary, setSummary] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadBreaks = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const breakItems = extractBreakList(await listBackendBreaks());
      const normalized = breakItems.map(normalizeBreak);
      setBreaks(normalized);
      setSummary({
        total: normalized.length,
        open: normalized.filter((item) => item.status === "open").length,
        investigating: normalized.filter((item) => item.status === "investigating").length,
        pending: normalized.filter((item) => item.status === "submitted_for_approval").length,
      });
    } catch (err) {
      setError(err.message || "Unable to load reconciliation breaks.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBreaks();
  }, [loadBreaks]);

  const filteredBreaks = useMemo(() => {
    return breaks.filter((item) => {
      const query = search.toLowerCase();

      const matchesSearch =
        !query ||
        item.id.toLowerCase().includes(query) ||
        item.key.toLowerCase().includes(query) ||
        item.runId.toLowerCase().includes(query);

      const matchesStatus =
        statusFilter === "all" ||
        item.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [breaks, search, statusFilter]);

  return (
    <div className="w-full max-w-[1500px] mx-auto text-white">
      <PageHeader
        eyebrow="RECONCILIATION"
        title="Breaks"
        description="Live reconciliation breaks from the OneRecon AI service."
        action={
          <button
            type="button"
            onClick={loadBreaks}
            disabled={loading}
            className="flex items-center gap-2 rounded-xl border border-[#1c684b] bg-[#0b3021] px-5 py-3 text-sm font-medium text-[#39df99] transition hover:border-[#28d995] hover:bg-[#10432f] disabled:opacity-50"
          >
            <RefreshCw size={17} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
        }
      />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          ["Total", summary.total ?? breaks.length],
          ["Open", summary.open ?? "—"],
          ["Investigating", summary.investigating ?? "—"],
          ["Pending Approval", summary.pending ?? "—"],
        ].map(([label, value]) => (
          <div
            key={label}
            className="rounded-2xl border border-[#153d30] bg-[#071b14] p-5"
          >
            <p className="text-[10px] uppercase tracking-wider text-[#52786a]">
              {label}
            </p>
            <p className="mt-2 text-2xl font-bold text-white">
              {value}
            </p>
          </div>
        ))}
      </div>

      <div className="overflow-hidden rounded-2xl border border-[#153d30] bg-[#071b14]">
        <div className="flex flex-col gap-4 border-b border-[#153d30] bg-[#081f17] p-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative w-full lg:max-w-md">
            <Search
              size={17}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#55796c]"
            />
            <input
              type="search"
              placeholder="Search break ID, run ID or key..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="w-full rounded-xl border border-[#173f31] bg-[#041710] py-3 pl-10 pr-4 text-sm text-white placeholder-[#4e7064] outline-none transition focus:border-[#237b58]"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="w-full rounded-xl border border-[#173f31] bg-[#041710] px-4 py-3 text-sm text-[#c5ddd3] outline-none lg:w-56"
          >
            <option value="all">All statuses</option>
            <option value="open">Open</option>
            <option value="investigating">Investigating</option>
            <option value="submitted_for_approval">Pending Approval</option>
            <option value="authorized">Authorized</option>
            <option value="closed">Closed</option>
          </select>
        </div>

        {error && (
          <div className="border-b border-red-500/20 bg-red-500/10 px-5 py-4 text-sm text-red-300">
            {error}
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full min-w-[1000px]">
            <thead>
              <tr className="border-b border-[#153d30] bg-[#081f17] text-left">
                {["Break ID", "Run ID", "Type", "Key", "Source A", "Source B", "Difference", "Status", ""].map(
                  (heading) => (
                    <th
                      key={heading}
                      className="px-5 py-4 text-[10px] font-semibold uppercase tracking-wider text-[#52786a]"
                    >
                      {heading}
                    </th>
                  )
                )}
              </tr>
            </thead>

            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="9" className="px-5 py-16 text-center text-sm text-[#5f8275]">
                    Loading breaks…
                  </td>
                </tr>
              ) : filteredBreaks.length === 0 ? (
                <tr>
                  <td colSpan="9" className="px-5 py-16 text-center text-sm text-[#5f8275]">
                    No breaks returned by the AI service.
                  </td>
                </tr>
              ) : (
                filteredBreaks.map((item) => (
                  <tr
                    key={item.id}
                    className="border-b border-[#102e24] last:border-b-0 transition hover:bg-[#092219]"
                  >
                    <td className="px-5 py-5">
                      <Link
                        to={`/investigator/investigation/${encodeURIComponent(item.id)}`}
                        className="text-sm font-semibold text-[#39df99] hover:text-[#79efba]"
                      >
                        {item.displayId}
                      </Link>
                    </td>
                    <td className="px-5 py-5 text-sm text-[#91aaa0]">{item.runId}</td>
                    <td className="px-5 py-5">
                      <span className="rounded-md border border-[#214b3c] bg-[#0a2119] px-2.5 py-1.5 text-[10px] font-medium text-[#82a99b]">
                        {item.reconciliationType}
                      </span>
                    </td>
                    <td className="px-5 py-5 font-mono text-sm text-[#d2e6df]">{item.key}</td>
                    <td className="px-5 py-5 font-mono text-sm text-[#b5cec4]">{String(item.sourceAValue)}</td>
                    <td className="px-5 py-5 font-mono text-sm text-[#b5cec4]">{String(item.sourceBValue)}</td>
                    <td className="px-5 py-5">
                      <span className="rounded-md bg-[#321717] px-2.5 py-1.5 font-mono text-sm font-medium text-[#f07171]">
                        {String(item.difference)}
                      </span>
                    </td>
                    <td className="px-5 py-5">
                      <StatusBadge status={item.status} />
                    </td>
                    <td className="px-5 py-5">
                      <Link
                        to={`/investigator/investigation/${encodeURIComponent(item.id)}`}
                        className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#194b38] bg-[#0a241b] text-[#39df99] transition hover:border-[#2a8b65] hover:bg-[#0d3023]"
                        title="Open investigation"
                      >
                        <ArrowRight size={17} />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between border-t border-[#153d30] bg-[#061811] px-5 py-4">
          <span className="text-xs text-[#5f8275]">
            Showing {filteredBreaks.length} break{filteredBreaks.length !== 1 ? "s" : ""}
          </span>
          <span className="text-xs text-[#52786a]">
            GET /breaks · GET /breaks/summary
          </span>
        </div>
      </div>
    </div>
  );
}

export default Breaks;
