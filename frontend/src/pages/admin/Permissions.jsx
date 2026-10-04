import {
  Check,
  ShieldCheck,
} from "lucide-react";
import PageHeader from "../../components/PageHeader";

const permissionGroups = {
  INVESTIGATOR: [
    "reconciliation.view",
    "breaks.view",
    "investigation.view",
    "investigation.create",
    "investigation.update",
    "evidence.view",
    "evidence.upload",
    "investigation.submit",
  ],

  APPROVER: [
    "reconciliation.view",
    "breaks.view",
    "investigation.view",
    "approval.view",
    "approval.approve",
    "approval.reject",
    "approval.history",
  ],

  ADMIN: [
    "users.view",
    "users.create",
    "users.update",
    "users.disable",
    "roles.view",
    "roles.manage",
    "permissions.view",
    "permissions.manage",
    "system.manage",
    "audit.view",
    "reconciliation.view",
    "reports.view",
  ],
};

function Permissions() {
  return (
    <div className="page">
      <PageHeader
        eyebrow="ADMINISTRATION"
        title="Permissions"
        description="Review the permissions assigned to each application role."
      />

      <div className="permission-grid">
        {Object.entries(permissionGroups).map(
          ([role, permissions]) => (
            <section
              className="content-card"
              key={role}
            >
              <div className="content-card-header">
                <div className="permission-role-title">
                  <div className="role-card-icon">
                    <ShieldCheck size={19} />
                  </div>

                  <div>
                    <h2>{role}</h2>
                    <p>
                      {permissions.length} permissions
                    </p>
                  </div>
                </div>
              </div>

              <div className="permission-list">
                {permissions.map((permission) => (
                  <div
                    className="permission-row"
                    key={permission}
                  >
                    <span className="permission-check">
                      <Check size={14} />
                    </span>

                    <code>{permission}</code>
                  </div>
                ))}
              </div>
            </section>
          )
        )}
      </div>
    </div>
  );
}

export default Permissions;