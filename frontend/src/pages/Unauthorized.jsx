import { Link } from "react-router-dom";
import { ShieldAlert, ArrowLeft } from "lucide-react";

function Unauthorized() {
  return (
    <div className="error-page">
      <div className="error-card">
        <div className="error-icon">
          <ShieldAlert size={42} />
        </div>

        <h1>Access Restricted</h1>

        <p>
          You do not have permission to access this page.
          Please contact your administrator if you believe
          this is incorrect.
        </p>

        <Link to="/" className="primary-button">
          <ArrowLeft size={17} />
          Return to Home
        </Link>
      </div>
    </div>
  );
}

export default Unauthorized;