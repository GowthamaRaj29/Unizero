import {
  Search,
} from "lucide-react";
import { useEffect, useState } from "react";
import PageHeader from "../../components/PageHeader";
import { getUsers } from "../../services/adminApi";

function Users() {
  const [users, setUsers] = useState([]);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    getUsers()
      .then((items) => {
        if (!active) return;

        setUsers(
          Array.isArray(items)
            ? items.map((user) => ({
                id: user.id,
                email: user.email || user.username,
                role: (user.role || "").toLowerCase(),
                status: user.is_active ? "active" : "disabled",
                createdAt: user.created_at
                  ? new Date(user.created_at).toLocaleDateString()
                  : "-",
                createdBy: "system",
              }))
            : []
        );
      })
      .catch((err) => {
        if (active) {
          setError(err.message || "Unable to load users.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const filteredUsers = users.filter((user) => {
    const matchesSearch = user.email
      .toLowerCase()
      .includes(search.toLowerCase());

    const matchesRole =
      roleFilter === "all" ||
      user.role === roleFilter;

    return matchesSearch && matchesRole;
  });

  return (
    <div className="page">
      <PageHeader
        eyebrow="ADMINISTRATION"
        title="Current Users"
        description="View users who currently have access to OneRecon."
      />

      <div className="content-card">
        {error && (
          <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        <div className="filter-bar">
          <div className="search-input">
            <Search size={17} />

            <input
              type="search"
              placeholder="Search by email..."
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
            />
          </div>

          <div className="filter-select">
            <select
              value={roleFilter}
              onChange={(event) =>
                setRoleFilter(event.target.value)
              }
            >
              <option value="all">All roles</option>
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
                <th>User ID</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Created By</th>
                <th>Created At</th>
              </tr>
            </thead>

            <tbody>
              {!loading && filteredUsers.map((user) => (
                <tr key={user.id}>
                  <td>{user.id}</td>

                  <td>
                    <div className="user-table-cell">
                      <div className="user-table-avatar">
                        {user.email
                          .slice(0, 2)
                          .toUpperCase()}
                      </div>

                      {user.email}
                    </div>
                  </td>

                  <td>
                    <span className="role-badge">
                      {user.role}
                    </span>
                  </td>

                  <td>
                    <span
                      className={`user-status ${
                        user.status === "active"
                          ? "user-status-active"
                          : "user-status-disabled"
                      }`}
                    >
                      {user.status}
                    </span>
                  </td>

                  <td>{user.createdBy}</td>
                  <td>{user.createdAt}</td>

                </tr>
              ))}

              {loading && (
                <tr>
                  <td
                    colSpan="6"
                    className="table-empty"
                  >
                    Loading users...
                  </td>
                </tr>
              )}

              {!loading && filteredUsers.length === 0 && (
                <tr>
                  <td
                    colSpan="6"
                    className="table-empty"
                  >
                    No users found.
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

export default Users;
