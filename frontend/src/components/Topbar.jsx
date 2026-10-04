import {
  Bell,
  Menu,
  Search,
} from "lucide-react";
import { useAuth } from "../auth/AuthContext";

function Topbar({ onMenuClick }) {
  const { user } = useAuth();

  const role =
    user?.role?.charAt(0).toUpperCase() +
      user?.role?.slice(1).toLowerCase() || "User";

  const initials =
    user?.email
      ?.split("@")[0]
      ?.slice(0, 2)
      ?.toUpperCase() || "UR";

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button
          type="button"
          className="mobile-menu-button"
          onClick={onMenuClick}
          aria-label="Open navigation"
        >
          <Menu size={21} />
        </button>

        <div className="topbar-search">
          <Search size={18} />
          <input
            type="search"
            placeholder="Search OneRecon..."
            aria-label="Search"
          />
          <span className="search-shortcut">⌘ K</span>
        </div>
      </div>

      <div className="topbar-right">
        <button
          type="button"
          className="notification-button"
          aria-label="Notifications"
        >
          <Bell size={19} />
          <span className="notification-dot" />
        </button>

        <div className="topbar-divider" />

        <div className="topbar-user">
          <div className="user-avatar">{initials}</div>

          <div className="topbar-user-info">
            <span className="topbar-user-email">
              {user?.email || "User"}
            </span>

            <span className="topbar-user-role">
              {role}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}

export default Topbar;