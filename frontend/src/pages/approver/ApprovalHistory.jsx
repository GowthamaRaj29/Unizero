import {
  CheckCircle2,
  Download,
  Search,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import PageHeader from "../../components/PageHeader";
import { getApprovalHistory } from "../../services/approvalApi";

function ApprovalHistory() {
  const [search, setSearch] = useState("");
  const [decision, setDecision] = useState("All");
  const [historyItems, setHistoryItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getApprovalHistory()
      .then((items) => setHistoryItems(Array.isArray(items) ? items : []))
      .catch((requestError) => setError(requestError.message || "Unable to load approval history."))
      .finally(() => setLoading(false));
  }, []);

  const filteredItems = useMemo(() => {
    return historyItems.filter((item) => {
      const text =
        `${item.id} ${item.break_id} ${item.key} ${item.actor}`
          .toLowerCase();

      const matchesSearch = text.includes(
        search.toLowerCase()
      );

      const matchesDecision =
        decision === "All" ||
        item.action === decision;

      return matchesSearch && matchesDecision;
    });
  }, [search, decision]);

  const approvedCount = historyItems.filter((item) => item.status === "APPROVED").length;
  const rejectedCount = historyItems.filter((item) => item.status === "REJECTED").length;
  const totalReviewed = approvedCount + rejectedCount;
  const approvalRate = totalReviewed
    ? `${((approvedCount / totalReviewed) * 100).toFixed(1)}%`
    : "0.0%";

  function exportHistory() {
    const rows = [
      [
        "Approval ID",
        "Break ID",
        "Run ID",
        "Key",
        "Decision",
        "Actor",
        "Comment",
        "Timestamp",
      ],
      ...filteredItems.map((item) => [
        item.id,
        item.break_id,
        item.run_id,
        item.key,
        item.action,
        item.actor,
        item.comment,
        item.timestamp,
      ]),
    ];

    const csv = rows
      .map((row) =>
        row
          .map((value) =>
            `"${String(value).replace(/"/g, '""')}"`
          )
          .join(",")
      )
      .join("\n");

    const blob = new Blob([csv], {
      type: "text/csv;charset=utf-8;",
    });

    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = url;
    link.download = "approval-history.csv";

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);
  }

  return (
    <div className="page">

      <PageHeader
        eyebrow="APPROVER WORKSPACE"
        title="Approval History"
        description="Review previous approval and rejection decisions."
        action={
          <button
            type="button"
            className="secondary-button"
            onClick={exportHistory}
          >
            <Download size={16} />
            Export CSV
          </button>
        }
      />

      {/* HISTORY SUMMARY */}
      <div className="stats-grid">

        <div className="stat-card">
          <div className="stat-card-value">
            {totalReviewed}
          </div>

          <div className="stat-card-title">
            Total Reviewed
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-value text-emerald-400">
            {approvedCount}
          </div>

          <div className="stat-card-title">
            Approved
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-value text-red-400">
            {rejectedCount}
          </div>

          <div className="stat-card-title">
            Rejected
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-value">
            {approvalRate}
          </div>

          <div className="stat-card-title">
            Approval Rate
          </div>
        </div>

      </div>

      <div className="content-card">

        {error && <div className="alert alert-error">{error}</div>}

        {/* FILTER */}
        <div className="filter-bar">

          <div className="search-input">
            <Search size={17} />

            <input
              type="search"
              placeholder="Search approval, break, key or actor..."
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
            />
          </div>

          <div className="search-input">

            <select
              value={decision}
              onChange={(event) =>
                setDecision(event.target.value)
              }
            >
              <option value="All">
                All Decisions
              </option>

              <option value="approved">
                Approved
              </option>

              <option value="rejected">
                Rejected
              </option>
            </select>

          </div>

        </div>

        {/* TABLE */}
        <div className="table-container">

          <table className="data-table">

            <thead>
              <tr>
                <th>Approval ID</th>
                <th>Break ID</th>
                <th>Run ID</th>
                <th>Key</th>
                <th>Decision</th>
                <th>Actor</th>
                <th>Comment</th>
                <th>Timestamp</th>
              </tr>
            </thead>

            <tbody>

              {loading ? (
                <tr>
                  <td colSpan="8" className="table-empty">
                    Loading approval history...
                  </td>
                </tr>
              ) : filteredItems.map((item) => (
                <tr key={item.id}>

                  <td>
                    <strong className="text-white">
                      {item.id}
                    </strong>
                  </td>

                  <td>{item.break_id}</td>

                  <td>{item.run_id || "—"}</td>

                  <td>{item.key}</td>

                  <td>
                    {item.action === "approved" || item.status === "APPROVED" ? (
                      <span className="status-badge status-approved">
                        <CheckCircle2 size={14} />
                        Approved
                      </span>
                    ) : (
                      <span className="status-badge status-rejected">
                        <XCircle size={14} />
                        Rejected
                      </span>
                    )}
                  </td>

                  <td>{item.actor}</td>

                  <td className="comment-cell">
                    {item.comment}
                  </td>

                  <td>{item.timestamp}</td>

                </tr>
              ))}

              {!loading && filteredItems.length === 0 && (
                <tr>
                  <td
                    colSpan="8"
                    className="table-empty"
                  >
                    No approval history found.
                  </td>
                </tr>
              )}

            </tbody>

          </table>

        </div>
      </div>

    </div>
  );
}

export default ApprovalHistory;