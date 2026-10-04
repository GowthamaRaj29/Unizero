import api from "./api";

export async function getApprovals(params = {}) {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (
      value !== undefined &&
      value !== null &&
      value !== ""
    ) {
      searchParams.append(key, value);
    }
  });

  const query = searchParams.toString();

  return api.get(
    `/approvals${query ? `?${query}` : ""}`
  );
}

export async function getApproval(id) {
  return api.get(`/approvals/${id}`);
}

export async function approveInvestigation(
  id,
  comment = ""
) {
  return api.post(`/approvals/${id}/approve`, {
    comment,
  });
}

export async function rejectInvestigation(
  id,
  comment
) {
  return api.post(`/approvals/${id}/reject`, {
    comment,
  });
}

export async function getApprovalHistory(
  params = {}
) {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (
      value !== undefined &&
      value !== null &&
      value !== ""
    ) {
      searchParams.append(key, value);
    }
  });

  const query = searchParams.toString();

  return api.get(
    `/approvals/history${query ? `?${query}` : ""}`
  );
}