import {
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

// Auth
import Login from "./pages/auth/Login";
import Unauthorized from "./pages/Unauthorized";

// Layouts
import AdminLayout from "./layouts/AdminLayout";
import ApproverLayout from "./layouts/ApproverLayout";
import InvestigatorLayout from "./layouts/InvestigatorLayout";

// Admin
import AdminDashboard from "./pages/admin/Dashboard";
import AdminUsers from "./pages/admin/Users";
import AdminAuditLogs from "./pages/admin/AuditLogs";

// Approver
import ApproverDashboard from "./pages/approver/Dashboard";
import ApprovalDetail from "./pages/approver/ApprovalDetail";
import ApprovalHistory from "./pages/approver/ApprovalHistory";

// Investigator
import InvestigatorDashboard from "./pages/investigator/Dashboard";
import InvestigatorBreaks from "./pages/investigator/Breaks";
import InvestigatorEvidence from "./pages/investigator/Evidence";
import InvestigatorInvestigation from "./pages/investigator/Investigation";
import InvestigatorMapping from "./pages/investigator/Mapping";

function App() {
  return (
    <Routes>

      {/* =========================
          PUBLIC ROUTES
      ========================== */}

      <Route
        path="/"
        element={<Navigate to="/login" replace />}
      />

      <Route
        path="/login"
        element={<Login />}
      />

      <Route
        path="/unauthorized"
        element={<Unauthorized />}
      />


      {/* =========================
          ADMIN
      ========================== */}

      <Route
        path="/admin"
        element={<AdminLayout />}
      >
        <Route
          index
          element={
            <Navigate
              to="/admin/dashboard"
              replace
            />
          }
        />

        <Route
          path="dashboard"
          element={<AdminDashboard />}
        />

        <Route
          path="users"
          element={<AdminUsers />}
        />

        <Route
          path="audit-logs"
          element={<AdminAuditLogs />}
        />
      </Route>


      {/* =========================
          APPROVER
      ========================== */}

      <Route
        path="/approver"
        element={<ApproverLayout />}
      >
        <Route
          index
          element={
            <Navigate
              to="/approver/dashboard"
              replace
            />
          }
        />

        <Route
          path="dashboard"
          element={<ApproverDashboard />}
        />

        <Route
          path="approvals/:id"
          element={<ApprovalDetail />}
        />

        <Route
          path="approval-history"
          element={<ApprovalHistory />}
        />
      </Route>


      {/* =========================
          INVESTIGATOR
      ========================== */}

      <Route
        path="/investigator"
        element={<InvestigatorLayout />}
      >

        {/* /investigator */}
        <Route
          index
          element={
            <Navigate
              to="/investigator/dashboard"
              replace
            />
          }
        />

        {/* Investigator Dashboard */}
        <Route
          path="dashboard"
          element={<InvestigatorDashboard />}
        />

        {/* Field Mapping */}
        <Route
          path="mapping"
          element={<InvestigatorMapping />}
        />

        {/* Break Management */}
        <Route
          path="breaks"
          element={<InvestigatorBreaks />}
        />

        {/* Evidence */}
        <Route
          path="evidence"
          element={<InvestigatorEvidence />}
        />

        {/* Investigation */}
        <Route
          path="investigation/:id"
          element={<InvestigatorInvestigation />}
        />

      </Route>


      {/* =========================
          FALLBACK
      ========================== */}

      <Route
        path="*"
        element={
          <Navigate
            to="/login"
            replace
          />
        }
      />

    </Routes>
  );
}

export default App;