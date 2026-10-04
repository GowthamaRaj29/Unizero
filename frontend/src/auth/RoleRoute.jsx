import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

function RoleRoute({ roles = [], children }) {
  const { user, isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="route-loading">
        <div className="route-loading-spinner" />
        <p>Loading OneRecon...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  const userRole = user?.role?.toLowerCase();

  const allowed = roles.some(
    (role) => role.toLowerCase() === userRole
  );

  if (!allowed) {
    return <Navigate to="/unauthorized" replace />;
  }

  return children;
}

export default RoleRoute;