import {
  BarChart3,
  ClipboardCheck,
  ClipboardList,
  FileSearch,
  FileText,
  LayoutDashboard,
  LogOut,
  Users,
  UserCheck,
  X,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const navigation = {
  investigator: [
    {
      label: "Dashboard",
      path: "/investigator/dashboard",
      icon: LayoutDashboard,
    },
    {
      label: "Breaks",
      path: "/investigator/breaks",
      icon: FileSearch,
    },
    {
      label: "Investigation",
      path: "/investigator/investigation",
      icon: ClipboardCheck,
    },
    {
      label: "Evidence",
      path: "/investigator/evidence",
      icon: FileText,
    },
  ],

  approver: [
    {
      label: "Dashboard",
      path: "/approver/dashboard",
      icon: LayoutDashboard,
    },
    {
      label: "Approval History",
      path: "/approver/approval-history",
      icon: FileText,
    },
  ],

  admin: [
    {
      label: "Registration Approvals",
      path: "/admin/dashboard",
      icon: UserCheck,
    },
    {
      label: "Current Users",
      path: "/admin/users",
      icon: Users,
    },
    {
      label: "Audit Logs",
      path: "/admin/audit-logs",
      icon: ClipboardList,
    },
  ],
};

function Sidebar({ mobileOpen = false, onClose }) {
  const { user, logout } = useAuth();

  const role = user?.role?.toLowerCase() || "investigator";

  const items = navigation[role] || [];

  const roleLabel =
    role.charAt(0).toUpperCase() + role.slice(1);

  return (
    <>
      {mobileOpen && (
        <div
          className="sidebar-overlay"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={`sidebar ${
          mobileOpen ? "sidebar-open" : ""
        }`}
      >
        <div className="sidebar-header">
          <div className="brand">
            <div className="brand-mark">
              <BarChart3 size={20} />
            </div>

            <div>
              <div className="brand-name">OneRecon</div>
              <div className="brand-subtitle">
                Reconciliation Platform
              </div>
            </div>
          </div>

          <button
            type="button"
            className="mobile-close-button"
            onClick={onClose}
            aria-label="Close navigation"
          >
            <X size={20} />
          </button>
        </div>

        <div className="sidebar-role">
          <span className="role-dot" />
          <span>{roleLabel}</span>
        </div>

        <nav className="sidebar-navigation">
          <div className="navigation-label">WORKSPACE</div>

          {items.map((item) => {
            const Icon = item.icon;

            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={onClose}
                className={({ isActive }) =>
                  `navigation-item ${
                    isActive ? "navigation-item-active" : ""
                  }`
                }
              >
                <Icon size={18} strokeWidth={1.8} />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <button
            type="button"
            className="logout-button"
            onClick={logout}
          >
            <LogOut size={18} />
            <span>Sign out</span>
          </button>
        </div>
      </aside>
    </>
  );
}

export default Sidebar;