import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, RefreshCw, Workflow as WorkflowIcon } from "lucide-react";

import PageHeader from "../../components/PageHeader";
import DataTable from "../../components/DataTable";
import EmptyState from "../../components/EmptyState";
import ErrorState from "../../components/ErrorState";

import { getWorkflows } from "../../services/workflowApi";

function Workflows() {
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadWorkflows() {
    try {
      setLoading(true);
      setError("");

      const response = await getWorkflows();

      setWorkflows(
        Array.isArray(response)
          ? response
          : response?.items || []
      );
    } catch (err) {
      setError(
        err?.message || "Unable to load workflows."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadWorkflows();
  }, []);

  const columns = [
    {
      key: "name",
      label: "Workflow",
    },
    {
      key: "period",
      label: "Period",
      render: (row) => row.period || "—",
    },
    {
      key: "status",
      label: "Status",
      render: (row) => (
        <span className={`status-badge ${String(row.status || "").toLowerCase()}`}>
          {row.status}
        </span>
      ),
    },
    {
      key: "created_at",
      label: "Created",
      render: (row) =>
        row.created_at
          ? new Date(row.created_at).toLocaleString()
          : "—",
    },
    {
      key: "actions",
      label: "",
      render: (row) => (
        <Link
          to={`/workflows/${row.id}`}
          className="table-link"
        >
          Open
        </Link>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Workflows"
        subtitle="Create and manage reconciliation workflows."
        actions={
          <div className="page-actions">
            <button
              type="button"
              className="secondary-button"
              onClick={loadWorkflows}
              disabled={loading}
            >
              <RefreshCw size={16} />
              Refresh
            </button>

            <Link
              to="/workflows/new"
              className="primary-button"
            >
              <Plus size={16} />
              New Workflow
            </Link>
          </div>
        }
      />

      {error && (
        <ErrorState
          title="Unable to load workflows"
          message={error}
          onRetry={loadWorkflows}
        />
      )}

      {!error && !loading && workflows.length === 0 && (
        <EmptyState
          icon={WorkflowIcon}
          title="No workflows yet"
          description="Create your first reconciliation workflow to get started."
          action={
            <Link
              to="/workflows/new"
              className="primary-button"
            >
              <Plus size={16} />
              Create Workflow
            </Link>
          }
        />
      )}

      {!error && (loading || workflows.length > 0) && (
        <DataTable
          columns={columns}
          data={workflows}
          loading={loading}
        />
      )}
    </div>
  );
}

export default Workflows;