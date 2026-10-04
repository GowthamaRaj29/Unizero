import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Save } from "lucide-react";

import PageHeader from "../../components/PageHeader";
import { createWorkflow } from "../../services/workflowApi";

function WorkflowCreate() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    name: "",
    period: "",
    status: "DRAFT",
  });

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function handleChange(event) {
    const { name, value } = event.target;

    setForm((current) => ({
      ...current,
      [name]: value,
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();

    if (!form.name.trim()) {
      setError("Workflow name is required.");
      return;
    }

    try {
      setSaving(true);
      setError("");

      const workflow = await createWorkflow({
        name: form.name.trim(),
        period: form.period.trim() || null,
        status: form.status,
      });

      navigate(
        `/workflows/${workflow.id}`
      );
    } catch (err) {
      setError(
        err?.message || "Unable to create workflow."
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Create Workflow"
        subtitle="Define a reconciliation workflow."
        actions={
          <button
            type="button"
            className="secondary-button"
            onClick={() => navigate("/workflows")}
          >
            <ArrowLeft size={16} />
            Back
          </button>
        }
      />

      <div className="form-card">
        <form onSubmit={handleSubmit}>
          {error && (
            <div className="form-error">
              {error}
            </div>
          )}

          <div className="form-grid">
            <div className="form-field">
              <label htmlFor="name">
                Workflow Name
              </label>

              <input
                id="name"
                name="name"
                value={form.name}
                onChange={handleChange}
                placeholder="e.g. Daily Cash Reconciliation"
                required
              />
            </div>

            <div className="form-field">
              <label htmlFor="period">
                Period
              </label>

              <input
                id="period"
                name="period"
                value={form.period}
                onChange={handleChange}
                placeholder="e.g. September 2026"
              />
            </div>

            <div className="form-field">
              <label htmlFor="status">
                Status
              </label>

              <select
                id="status"
                name="status"
                value={form.status}
                onChange={handleChange}
              >
                <option value="DRAFT">
                  Draft
                </option>
                <option value="ACTIVE">
                  Active
                </option>
              </select>
            </div>
          </div>

          <div className="form-actions">
            <button
              type="button"
              className="secondary-button"
              onClick={() => navigate("/workflows")}
              disabled={saving}
            >
              Cancel
            </button>

            <button
              type="submit"
              className="primary-button"
              disabled={saving}
            >
              <Save size={16} />
              {saving
                ? "Creating..."
                : "Create Workflow"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default WorkflowCreate;