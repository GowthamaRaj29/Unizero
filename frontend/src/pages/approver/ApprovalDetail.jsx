import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Loader2,
} from "lucide-react";

import PageHeader from "../../components/PageHeader";
import StatusBadge from "../../components/StatusBadge";
import {
  getApproval,
  approveInvestigation,
  rejectInvestigation,
} from "../../services/approvalApi";

function ApprovalDetail() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [approval, setApproval] = useState(null);
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadApproval() {
      try {
        setLoading(true);
        setError("");

        const response = await getApproval(id);
        const remoteApproval = response?.data || response;

        setApproval({
          ...remoteApproval,
          break_id: remoteApproval?.break_id || remoteApproval?.break?.id,
          run_id: remoteApproval?.run_id || remoteApproval?.break?.run_id,
          reconciliation_key:
            remoteApproval?.reconciliation_key || remoteApproval?.break?.key,
          ai_root_cause:
            remoteApproval?.ai_root_cause || remoteApproval?.break?.ai_explanation,
          investigator_explanation:
            remoteApproval?.investigator_explanation || remoteApproval?.justification,
        });
      } catch (err) {
        setError(err.message || "Unable to load approval.");
      } finally {
        setLoading(false);
      }
    }

    loadApproval();
  }, [id]);

  async function handleApprove() {
    try {
      setProcessing(true);
      setError("");

      await approveInvestigation(id, comment);

      navigate("/approver/approval-history");
    } catch (err) {
      setError(
        err.message || "Unable to approve investigation."
      );
    } finally {
      setProcessing(false);
    }
  }

  async function handleReject() {
    if (!comment.trim()) {
      setError("A rejection explanation is required.");
      return;
    }

    try {
      setProcessing(true);
      setError("");

      await rejectInvestigation(id, comment);

      navigate("/approver/approval-history");
    } catch (err) {
      setError(
        err.message || "Unable to reject investigation."
      );
    } finally {
      setProcessing(false);
    }
  }

  if (loading) {
    return (
      <div className="route-loading">
        <Loader2 className="spin" size={28} />
        <p>Loading approval...</p>
      </div>
    );
  }

  if (!approval) {
    return (
      <div className="page-state">
        <h2>Approval not found</h2>
        <Link to="/approver/dashboard">
          Return to Approver Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Approver"
        title={`Approval ${approval.id || id}`}
        description="Review the investigation and authorize or reject the submitted resolution."
      />

      {error && (
        <div className="alert alert-error">
          {error}
        </div>
      )}

      <div className="detail-card">
        <div className="detail-card-header">
          <div>
            <span className="detail-label">Status</span>
            <StatusBadge status={approval.status} />
          </div>

          <Link
            to="/approver/dashboard"
            className="secondary-button"
          >
            <ArrowLeft size={16} />
            Back
          </Link>
        </div>

        <div className="detail-grid">
          <div>
            <span className="detail-label">Break ID</span>
            <strong>{approval.break_id || "—"}</strong>
          </div>

          <div>
            <span className="detail-label">Run ID</span>
            <strong>{approval.run_id || "—"}</strong>
          </div>

          <div>
            <span className="detail-label">
              Reconciliation Key
            </span>
            <strong>
              {approval.reconciliation_key || "—"}
            </strong>
          </div>

          <div>
            <span className="detail-label">Investigator</span>
            <strong>
              {approval.investigator_email || approval.investigator || "—"}
            </strong>
          </div>
        </div>

        <div className="detail-section-heading">
          <div>
            <span className="detail-label">Investigation assessment</span>
            <h2>Understand the break before deciding</h2>
          </div>
          <span className="detail-section-note">Evidence submitted by the investigator</span>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-[#153d30] bg-[#041710] p-5">
            <div className="text-xs font-semibold uppercase tracking-wider text-[#28d995]">
              AI Explanation
            </div>
            <p className="mt-3 text-sm leading-6 text-[#b0c4bc]">
              {approval.ai_root_cause || approval.aiExplanation || "No AI explanation available."}
            </p>
          </div>

          <div className="rounded-xl border border-[#153d30] bg-[#041710] p-5">
            <div className="text-xs font-semibold uppercase tracking-wider text-[#28d995]">
              Investigator Explanation
            </div>
            <p className="mt-3 text-sm leading-6 text-[#b0c4bc]">
              {approval.investigator_explanation ||
                approval.investigatorExplanation ||
                "No investigator explanation available."}
            </p>
          </div>
        </div>

        <div className="mt-5 grid gap-4 rounded-xl border border-[#153d30] bg-[#041710] p-5 sm:grid-cols-3">
          <div>
            <span className="detail-label">Field</span>
            <strong>{approval.field || "—"}</strong>
          </div>
          <div>
            <span className="detail-label">Source A</span>
            <strong>{approval.sourceAValue || approval.source_a_value || "—"}</strong>
          </div>
          <div>
            <span className="detail-label">Source B</span>
            <strong>{approval.sourceBValue || approval.source_b_value || "—"}</strong>
          </div>
        </div>

        <div className="form-group mt-6">
          <div className="form-group-heading">
            <div>
              <label htmlFor="approval-comment">Decision explanation</label>
              <p>Your explanation will be recorded in approval history.</p>
            </div>
            <span className="detail-section-note">Required for rejection</span>
          </div>

          <textarea
            id="approval-comment"
            value={comment}
            onChange={(event) =>
              setComment(event.target.value)
            }
            placeholder="Enter your review explanation..."
            rows={5}
          />
        </div>

        <div className="action-row">
          <button
            type="button"
            className="danger-button"
            onClick={handleReject}
            disabled={processing}
          >
            <XCircle size={17} />
            Reject
          </button>

          <button
            type="button"
            className="primary-button"
            onClick={handleApprove}
            disabled={processing}
          >
            {processing ? (
              <Loader2 size={17} className="spin" />
            ) : (
              <CheckCircle2 size={17} />
            )}
            Approve
          </button>
        </div>
      </div>
    </div>
  );
}

export default ApprovalDetail;