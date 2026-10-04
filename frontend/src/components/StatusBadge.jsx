import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  FileCheck2,
  LoaderCircle,
  XCircle,
} from "lucide-react";

const statusConfig = {
  match: {
    label: "Matched",
    className: "status-match",
    icon: CheckCircle2,
  },

  matched: {
    label: "Matched",
    className: "status-match",
    icon: CheckCircle2,
  },

  break: {
    label: "Break",
    className: "status-break",
    icon: AlertCircle,
  },

  open: {
    label: "Open",
    className: "status-open",
    icon: AlertCircle,
  },

  investigating: {
    label: "Investigating",
    className: "status-investigating",
    icon: LoaderCircle,
  },

  resolved: {
    label: "Resolved",
    className: "status-resolved",
    icon: CheckCircle2,
  },

  submitted_for_approval: {
    label: "Pending Approval",
    className: "status-pending",
    icon: Clock3,
  },

  pending_approval: {
    label: "Pending Approval",
    className: "status-pending",
    icon: Clock3,
  },

  approved: {
    label: "Approved",
    className: "status-approved",
    icon: FileCheck2,
  },

  rejected: {
    label: "Rejected",
    className: "status-rejected",
    icon: XCircle,
  },

  closed: {
    label: "Closed",
    className: "status-closed",
    icon: CheckCircle2,
  },

  failed: {
    label: "Failed",
    className: "status-failed",
    icon: XCircle,
  },

  clean: {
    label: "Clean",
    className: "status-match",
    icon: CheckCircle2,
  },

  review_required: {
    label: "Review Required",
    className: "status-pending",
    icon: AlertCircle,
  },
};

function StatusBadge({ status }) {
  const normalizedStatus =
    String(status || "unknown")
      .toLowerCase()
      .replace(/\s+/g, "_");

  const config = statusConfig[normalizedStatus] || {
    label: status || "Unknown",
    className: "status-default",
    icon: Clock3,
  };

  const Icon = config.icon;

  return (
    <span className={`status-badge ${config.className}`}>
      <Icon size={14} />
      <span>{config.label}</span>
    </span>
  );
}

export default StatusBadge;