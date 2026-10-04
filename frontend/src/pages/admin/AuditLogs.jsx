import {
  Eye,
  Search,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import PageHeader from "../../components/PageHeader";
import { getAuditLogs } from "../../services/adminApi";

function AuditLogs() {
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("all");
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getAuditLogs()
      .then((logs) => setAuditLogs(Array.isArray(logs) ? logs : []))
      .catch((requestError) => setError(requestError.message || "Unable to load audit logs."))
      .finally(() => setLoading(false));
  }, []);

  const filteredLogs = useMemo(() => auditLogs.filter((log) => {
    const matchesSearch =
      log.id
        .toLowerCase()
        .includes(search.toLowerCase()) ||
      log.action
        .toLowerCase()
        .includes(search.toLowerCase()) ||
      (log.workflow_id || log.new_value || log.old_value || "")
        .toLowerCase()
        .includes(search.toLowerCase());

    return matchesSearch && (role === "all" || log.action.toLowerCase().includes(role));
  }), [auditLogs, role, search]);

  return (
    <div className="page">
      <PageHeader
        eyebrow="ADMINISTRATION"
        title="Audit Logs"
        description="Review the unified audit trail across OneRecon."
      />

      <div className="content-card">
        {error && <div className="alert alert-error">{error}</div>}
        <div className="filter-bar">
          <div className="search-input">
            <Search size={17} />

            <input
              type="search"
              placeholder="Search audit ID, actor, action or entity..."
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
            />
          </div>

          <div className="filter-select">
            <select
              value={role}
              onChange={(event) =>
                setRole(event.target.value)
              }
            >
              <option value="all">All actors</option>
              <option value="admin">Admin</option>
              <option value="investigator">
                Investigator
              </option>
              <option value="approver">
                Approver
              </option>
            </select>
          </div>
        </div>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Audit ID</th>
                <th>Actor</th>
                <th>Role</th>
                <th>Action</th>
                <th>Entity</th>
                <th>Entity ID</th>
                <th>Reason</th>
                <th>Timestamp</th>
                <th />
              </tr>
            </thead>

            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="9" className="table-empty">Loading audit events...</td>
                </tr>
              ) : filteredLogs.map((log) => (
                <tr key={log.id}>
                  <td>{log.id}</td>
                  <td>{log.user_id || "—"}</td>

                  <td>
                    <span className="role-badge">
                      {log.workflow_id ? "workflow" : "system"}
                    </span>
                  </td>

                  <td>
                    <code className="audit-action">
                      {log.action}
                    </code>
                  </td>

                  <td>{log.workflow_id ? "workflow" : "event"}</td>
                  <td>{log.workflow_id || log.new_value || log.old_value || "—"}</td>
                  <td>{log.reason}</td>
                  <td>{log.timestamp}</td>

                  <td>
                    <button
                      type="button"
                      className="table-action"
                      title="View audit event"
                    >
                      <Eye size={16} />
                    </button>
                  </td>
                </tr>
              ))}

              {!loading && filteredLogs.length === 0 && (
                <tr>
                  <td
                    colSpan="9"
                    className="table-empty"
                  >
                    No audit events found.
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

export default AuditLogs;