import api from "./api";

export async function getUsers(params = {}) {
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
    `/admin/users${query ? `?${query}` : ""}`
  );
}

export async function createUser(payload) {
  return api.post("/admin/users", payload);
}

export async function updateUser(id, payload) {
  return api.put(`/admin/users/${id}`, payload);
}

export async function disableUser(id) {
  return api.post(`/admin/users/${id}/disable`, {});
}

export async function getPendingRegistrations() {
  return api.get("/admin/pending-registrations");
}

export async function approveRegistration(id) {
  return api.post(`/admin/pending-registrations/${id}/approve`, {});
}

export async function rejectRegistration(id) {
  return api.post(`/admin/pending-registrations/${id}/reject`, {});
}

export async function getRoles() {
  return api.get("/admin/roles");
}

export async function createRole(payload) {
  return api.post("/admin/roles", payload);
}

export async function updateRole(id, payload) {
  return api.put(`/admin/roles/${id}`, payload);
}

export async function getPermissions() {
  return api.get("/admin/permissions");
}

export async function updateRolePermissions(
  roleId,
  permissions
) {
  return api.put(
    `/admin/roles/${roleId}/permissions`,
    {
      permissions,
    }
  );
}

export async function getAuditLogs(params = {}) {
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
    `/admin/audit-logs${query ? `?${query}` : ""}`
  );
}