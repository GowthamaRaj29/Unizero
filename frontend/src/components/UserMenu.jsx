import { ChevronDown, LogOut, UserCircle } from "lucide-react";
import { useState } from "react";
import { useAuth } from "../auth/AuthContext";

function UserMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);

  const initials =
    user?.email
      ?.split("@")[0]
      ?.slice(0, 2)
      ?.toUpperCase() || "UR";

  const role =
    user?.role?.charAt(0).toUpperCase() +
      user?.role?.slice(1).toLowerCase() || "User";

  return (
    <div className="user-menu">
      <button
        type="button"
        className="user-menu-trigger"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <span className="user-menu-avatar">{initials}</span>

        <span className="user-menu-details">
          <strong>{user?.email || "User"}</strong>
          <small>{role}</small>
        </span>

        <ChevronDown size={16} />
      </button>

      {open && (
        <div className="user-menu-dropdown">
          <div className="user-menu-profile">
            <UserCircle size={18} />
            <div>
              <strong>{user?.email || "User"}</strong>
              <span>{role}</span>
            </div>
          </div>

          <div className="user-menu-divider" />

          <button
            type="button"
            className="user-menu-action user-menu-logout"
            onClick={logout}
          >
            <LogOut size={17} />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

export default UserMenu;