import {
  Database,
  Save,
  Settings,
  ShieldCheck,
} from "lucide-react";
import { useState } from "react";
import PageHeader from "../../components/PageHeader";

function SystemSettings() {
  const [settings, setSettings] = useState({
    reconciliationTolerance: "0.00",
    defaultLoadType: "full",
    maxFileSize: "50",
    enableGemini: true,
    requireApproval: true,
    auditEnabled: true,
  });

  const handleChange = (event) => {
    const { name, value, type, checked } = event.target;

    setSettings((current) => ({
      ...current,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  const handleSubmit = (event) => {
    event.preventDefault();

    alert("System settings saved.");
  };

  return (
    <div className="page">
      <PageHeader
        eyebrow="ADMINISTRATION"
        title="System Settings"
        description="Configure reconciliation, ingestion, AI and audit behavior."
      />

      <form onSubmit={handleSubmit}>
        <div className="settings-grid">
          <section className="content-card">
            <div className="content-card-header">
              <div className="settings-section-title">
                <div className="settings-icon">
                  <Database size={19} />
                </div>

                <div>
                  <h2>Reconciliation</h2>
                  <p>
                    Configure deterministic reconciliation
                    behavior.
                  </p>
                </div>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="reconciliationTolerance">
                Reconciliation Tolerance
              </label>

              <input
                id="reconciliationTolerance"
                name="reconciliationTolerance"
                type="number"
                step="0.01"
                min="0"
                value={settings.reconciliationTolerance}
                onChange={handleChange}
              />

              <span className="form-help">
                Difference allowed before a result is
                classified as BREAK.
              </span>
            </div>

            <div className="form-group">
              <label htmlFor="defaultLoadType">
                Default Load Type
              </label>

              <select
                id="defaultLoadType"
                name="defaultLoadType"
                value={settings.defaultLoadType}
                onChange={handleChange}
              >
                <option value="full">Full</option>
                <option value="incremental">
                  Incremental
                </option>
              </select>
            </div>
          </section>

          <section className="content-card">
            <div className="content-card-header">
              <div className="settings-section-title">
                <div className="settings-icon">
                  <Settings size={19} />
                </div>

                <div>
                  <h2>Ingestion</h2>
                  <p>
                    Configure file ingestion constraints.
                  </p>
                </div>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="maxFileSize">
                Maximum File Size
              </label>

              <div className="input-with-suffix">
                <input
                  id="maxFileSize"
                  name="maxFileSize"
                  type="number"
                  min="1"
                  value={settings.maxFileSize}
                  onChange={handleChange}
                />

                <span>MB</span>
              </div>
            </div>
          </section>

          <section className="content-card">
            <div className="content-card-header">
              <div className="settings-section-title">
                <div className="settings-icon">
                  <ShieldCheck size={19} />
                </div>

                <div>
                  <h2>Platform Controls</h2>
                  <p>
                    Configure workflow and security behavior.
                  </p>
                </div>
              </div>
            </div>

            <div className="settings-toggle-list">
              <label className="settings-toggle">
                <div>
                  <strong>Gemini AI Assistance</strong>
                  <span>
                    Enable AI-assisted mapping, explanations
                    and RCA.
                  </span>
                </div>

                <input
                  type="checkbox"
                  name="enableGemini"
                  checked={settings.enableGemini}
                  onChange={handleChange}
                />

                <span className="toggle-slider" />
              </label>

              <label className="settings-toggle">
                <div>
                  <strong>Maker-Checker Approval</strong>
                  <span>
                    Require independent approval of
                    investigation resolutions.
                  </span>
                </div>

                <input
                  type="checkbox"
                  name="requireApproval"
                  checked={settings.requireApproval}
                  onChange={handleChange}
                />

                <span className="toggle-slider" />
              </label>

              <label className="settings-toggle">
                <div>
                  <strong>Audit Logging</strong>
                  <span>
                    Record system and workflow activities.
                  </span>
                </div>

                <input
                  type="checkbox"
                  name="auditEnabled"
                  checked={settings.auditEnabled}
                  onChange={handleChange}
                />

                <span className="toggle-slider" />
              </label>
            </div>
          </section>
        </div>

        <div className="settings-actions">
          <button
            type="submit"
            className="primary-button"
          >
            <Save size={17} />
            Save Settings
          </button>
        </div>
      </form>
    </div>
  );
}

export default SystemSettings;