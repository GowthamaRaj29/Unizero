import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  FileCheck2,
  History,
  Search,
  XCircle,
} from "lucide-react";

import { Link } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import PageHeader from "../../components/PageHeader";
import {
  getApprovalHistory,
  getApprovals,
} from "../../services/approvalApi";

function Dashboard() {
  const [search, setSearch] = useState("");
  const [approvals, setApprovals] = useState([]);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    Promise.all([getApprovals({ pending: true }), getApprovalHistory()])
      .then(([pending, completed]) => {
        if (!active) return;
        setApprovals(Array.isArray(pending) ? pending : []);
        setHistory(Array.isArray(completed) ? completed : []);
      })
      .catch((requestError) => {
        if (active) {
          setError(requestError.message || "Unable to load approvals.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const filteredApprovals = useMemo(() => {
    const query = search.trim().toLowerCase();

    if (!query) {
      return approvals;
    }

    return approvals.filter((item) =>
      `${item.break_id} ${item.break?.run_id} ${item.break?.key} ${item.investigator_email}`
        .toLowerCase()
        .includes(query)
    );
  }, [approvals, search]);

  const approvedCount = history.filter((item) => item.status === "APPROVED").length;
  const rejectedCount = history.filter((item) => item.status === "REJECTED").length;

  return (
    <div className="w-full max-w-[1500px] mx-auto text-white">

      {/* HEADER */}
      <PageHeader
        eyebrow="APPROVER WORKSPACE"
        title="Approver Dashboard"
        description="Review investigation submissions and authorize reconciliation resolutions."
        action={
          <div className="flex gap-3">

            <Link
              to="/approver/approval-history"
              className="flex items-center gap-2 rounded-xl border border-[#164b38] bg-[#071b14] px-4 py-2.5 text-sm font-medium text-[#28d995]"
            >
              <History size={16} />
              Approval History
            </Link>

          </div>
        }
      />

      {/* SUMMARY CARDS */}
      <section className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">

        <div className="rounded-2xl border border-[#153d30] bg-[#071b14] p-5">

            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-[#0b2a1e]">
              <Clock3
                size={20}
                className="text-[#28d995]"
              />
            </div>

            <div className="text-3xl font-semibold text-white">
              {approvals.length}
            </div>

            <div className="mt-1 text-sm font-medium text-white">
              Pending Approval
            </div>

            <div className="mt-2 text-xs text-[#52786a]">
              Awaiting your review
            </div>

        </div>


        <div className="rounded-2xl border border-[#153d30] bg-[#071b14] p-5">

          <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-[#0b2a1e]">
            <CheckCircle2
              size={20}
              className="text-[#28d995]"
            />
          </div>

          <div className="text-3xl font-semibold text-white">
            {approvedCount}
          </div>

          <div className="mt-1 text-sm font-medium text-white">
            Approved
          </div>

          <div className="mt-2 text-xs text-[#52786a]">
            This period
          </div>

        </div>


        <div className="rounded-2xl border border-[#153d30] bg-[#071b14] p-5">

          <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-[#321717]">
            <XCircle
              size={20}
              className="text-[#f07171]"
            />
          </div>

          <div className="text-3xl font-semibold text-white">
            {rejectedCount}
          </div>

          <div className="mt-1 text-sm font-medium text-white">
            Rejected
          </div>

          <div className="mt-2 text-xs text-[#52786a]">
            This period
          </div>

        </div>


        <div className="rounded-2xl border border-[#153d30] bg-[#071b14] p-5">

          <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-[#0b2a1e]">
            <FileCheck2
              size={20}
              className="text-[#28d995]"
            />
          </div>

          <div className="text-3xl font-semibold text-white">
            {approvedCount + rejectedCount}
          </div>

          <div className="mt-1 text-sm font-medium text-white">
            Total Reviewed
          </div>

          <div className="mt-2 text-xs text-[#52786a]">
            Completed decisions
          </div>

        </div>

      </section>


      {/* ONLY THIS SECTION REMAINS */}
      <section className="rounded-2xl border border-[#153d30] bg-[#071b14]">

        <div className="flex items-center justify-between border-b border-[#153d30] px-6 py-5">

          <div>

            <h2 className="text-lg font-semibold text-white">
              Pending Approvals — Priority Queue
            </h2>

            <p className="mt-1 text-sm text-[#729487]">
              Investigation submissions waiting for authorization.
            </p>

          </div>

        </div>

        {error && (
          <div className="border-b border-red-500/30 bg-red-500/10 px-5 py-3 text-sm text-red-300">
            {error}
          </div>
        )}


        {/* SEARCH */}
        <div className="border-b border-[#153d30] p-5">

          <div className="flex max-w-md items-center gap-3 rounded-xl border border-[#153d30] bg-[#041710] px-4 py-3">

            <Search
              size={17}
              className="text-[#52786a]"
            />

            <input
              type="text"
              placeholder="Search break, key, run..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="w-full bg-transparent text-sm text-white outline-none placeholder:text-[#52786a]"
            />

          </div>

        </div>


        {/* QUEUE TABLE */}
        <div className="overflow-x-auto">

          <table className="w-full text-left">

            <thead>

              <tr className="border-b border-[#153d30] text-xs uppercase tracking-wider text-[#52786a]">

                <th className="px-5 py-4">
                  Priority
                </th>

                <th className="px-5 py-4">
                  Break ID
                </th>

                <th className="px-5 py-4">
                  Run ID
                </th>

                <th className="px-5 py-4">
                  Result
                </th>

                <th className="px-5 py-4">
                  Key
                </th>

                <th className="px-5 py-4">
                  Difference
                </th>

                <th className="px-5 py-4">
                  Investigator
                </th>

                <th className="px-5 py-4">
                  Waiting
                </th>

                <th className="px-5 py-4">
                  Review
                </th>

              </tr>

            </thead>


            <tbody>

              {loading ? (
                <tr>
                  <td colSpan="9" className="px-5 py-8 text-center text-sm text-[#729487]">
                    Loading approvals...
                  </td>
                </tr>
              ) : filteredApprovals.map((item) => (

                <tr
                  key={item.id}
                  className="border-b border-[#102d23] transition hover:bg-[#092219]"
                >

                  <td className="px-5 py-4">

                    <span
                      className={
                        item.priority === "High"
                          ? "rounded-full border border-red-500/30 bg-red-500/10 px-3 py-1 text-xs text-red-300"
                          : "rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs text-amber-300"
                      }
                    >
                      {item.break?.status || "OPEN"}
                    </span>

                  </td>

                  <td className="px-5 py-4 font-semibold text-white">
                    {item.break_id}
                  </td>

                  <td className="px-5 py-4 text-sm text-[#91aaa0]">
                    {item.break?.run_id || "—"}
                  </td>

                  <td className="px-5 py-4 text-sm text-[#91aaa0]">
                    {item.investigation_id}
                  </td>

                  <td className="px-5 py-4 text-sm text-[#91aaa0]">
                    {item.break?.key || "—"}
                  </td>

                  <td className="px-5 py-4 font-semibold text-white">
                    {item.break?.difference ?? "—"}
                  </td>

                  <td className="px-5 py-4 text-sm text-[#91aaa0]">
                    {item.investigator_email || "—"}
                  </td>

                  <td className="px-5 py-4 text-sm text-[#91aaa0]">
                    {item.created_at || "—"}
                  </td>

                  <td className="px-5 py-4">

                    <Link
                      to={`/approver/approvals/${item.investigation_id}`}
                      className="inline-flex items-center gap-2 rounded-xl bg-[#28d995] px-4 py-2.5 text-sm font-semibold text-[#03130f] hover:bg-[#35dc96]"
                    >
                      Review
                      <ArrowRight size={14} />
                    </Link>

                  </td>

                </tr>

              ))}

              {!loading && filteredApprovals.length === 0 && (
                <tr>
                  <td colSpan="9" className="px-5 py-8 text-center text-sm text-[#729487]">
                    No pending approvals match your search.
                  </td>
                </tr>
              )}

            </tbody>

          </table>

        </div>

      </section>

    </div>
  );
}


export default Dashboard;