import { useState } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import Topbar from "../components/Topbar";

function AppLayout() {
  const [mobileSidebarOpen, setMobileSidebarOpen] =
    useState(false);

  return (
    <div className="app-shell">
      <Sidebar
        mobileOpen={mobileSidebarOpen}
        onClose={() => setMobileSidebarOpen(false)}
      />

      <div className="app-main">
        <Topbar
          onMenuClick={() =>
            setMobileSidebarOpen(true)
          }
        />

        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default AppLayout;