import {
  Edit3,
  Plus,
  ShieldCheck,
} from "lucide-react";
import PageHeader from "../../components/PageHeader";

const roles = [
  {
    id: 1,
    name: "ADMIN",
    description:
      "Manage users, roles, permissions, system configuration and audit activity.",
    userCount: 1,
    permissionCount: 11,
  },
  {
    id: 2,
    name: "APPROVER",
    description:
      "Review and authorize investigation resolutions.",
    userCount: 1,
    permissionCount: 7,
  },
  {
    id: 3,
    name: "INVESTIGATOR",
    description:
      "Investigate reconciliation breaks and submit resolutions.",
    userCount: 1,
    permissionCount: 8,
  },
];

function Roles() {
  return (
    <div className="page">
      <PageHeader
        eyebrow="ADMINISTRATION"
        title="Roles"
        description="Manage application roles and their associated permissions."
        action={
          <button
            type="button"
            className="primary-button"
          >
            <Plus size={17} />
            Create Role
          </button>
        }
      />

      <div className="role-cards-grid">
        {roles.map((role) => (
          <div className="role-card" key={role.id}>
            <div className="role-card-header">
              <div className="role-card-icon">
                <ShieldCheck size={21} />
              </div>

              <button
                type="button"
                className="table-action"
                title="Edit role"
              >
                <Edit3 size={16} />
              </button>
            </div>

            <h2>{role.name}</h2>

            <p>{role.description}</p>

            <div className="role-card-stats">
              <div>
                <strong>{role.userCount}</strong>
                <span>Users</span>
              </div>

              <div>
                <strong>
                  {role.permissionCount}
                </strong>
                <span>Permissions</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default Roles;