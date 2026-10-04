import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import AppLayout from "./AppLayout";

function AdminLayout() {
  const { user, isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (user?.role?.toLowerCase() !== "admin") {
    return <Navigate to="/unauthorized" replace />;
  }

  return (
    <AppLayout>
      <Outlet />
    </AppLayout>
  );
}

export default AdminLayout;