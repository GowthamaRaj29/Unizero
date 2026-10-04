import { LoaderCircle } from "lucide-react";

function LoadingScreen({
  message = "Loading OneRecon...",
}) {
  return (
    <div className="loading-screen">
      <div className="loading-screen-content">
        <div className="loading-logo">
          <LoaderCircle
            size={28}
            className="loading-spinner"
          />
        </div>

        <h2>OneRecon</h2>
        <p>{message}</p>
      </div>
    </div>
  );
}

export default LoadingScreen;