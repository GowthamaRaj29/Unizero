import { Check, Clock3, X } from "lucide-react";
import { useEffect, useState } from "react";
import PageHeader from "../../components/PageHeader";
import {
  approveRegistration,
  getPendingRegistrations,
  rejectRegistration,
} from "../../services/adminApi";

function Dashboard() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updatingId, setUpdatingId] = useState(null);

  const loadRequests = async () => {
    setLoading(true);
    setError("");

    try {
      const pending = await getPendingRegistrations();
      setRequests(
        pending.map((request) => ({
          id: request.id,
          name: request.full_name || request.email,
          email: request.email,
          role: request.role,
          requestedAt: request.requested_at,
        }))
      );
    } catch (requestError) {
      setError(requestError.message || "Unable to load registration requests.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRequests();
  }, []);

  const updateRequest = async (requestId, action) => {
    setUpdatingId(requestId);
    setError("");

    try {
      if (action === "approve") {
        await approveRegistration(requestId);
      } else {
        await rejectRegistration(requestId);
      }

      setRequests((current) =>
        current.filter((request) => request.id !== requestId)
      );
    } catch (requestError) {
      setError(requestError.message || "Unable to update registration request.");
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <div className="page dashboard-page">
      <PageHeader
        eyebrow="ADMINISTRATION"
        title="Registration Approvals"
        description="Review new account requests and approve access to OneRecon."
      />

      <section className="content-card">
        <div className="content-card-header">
          <div>
            <h2>Pending registration requests</h2>
            <p>Approve trusted users or reject requests that should not receive access.</p>
          </div>

          <span className="status-badge status-pending">
            <Clock3 size={14} />
            {requests.length} pending
          </span>
        </div>

        {error && (
          <p className="mb-4 rounded-lg border border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-300">
            {error}
          </p>
        )}

        {loading ? (
          <div className="rounded-xl border border-line bg-black/20 px-5 py-12 text-center text-sm text-slate-400">
            Loading registration requests...
          </div>
        ) : requests.length === 0 ? (
          <div className="rounded-xl border border-line bg-black/20 px-5 py-12 text-center">
            <Check className="mx-auto text-emerald-400" size={28} />
            <p className="mt-3 text-sm font-semibold text-white">All requests are reviewed.</p>
            <p className="mt-1 text-xs text-slate-500">New registration requests will appear here.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {requests.map((request) => (
              <div
                key={request.id}
                className="flex flex-col gap-4 rounded-xl border border-line bg-black/20 p-5 lg:flex-row lg:items-center lg:justify-between"
              >
                <div>
                  <h3 className="font-semibold text-white">{request.name}</h3>
                  <p className="mt-1 text-sm text-slate-400">{request.email}</p>
                  <p className="mt-2 text-xs uppercase tracking-[0.14em] text-slate-600">
                    {request.role} · Requested {request.requestedAt}
                  </p>
                </div>

                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={updatingId === request.id}
                    onClick={() => updateRequest(request.id, "approve")}
                    className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-bold text-[#06110b] transition hover:bg-emerald-400"
                  >
                    <Check size={16} />
                    Approve
                  </button>
                  <button
                    type="button"
                    disabled={updatingId === request.id}
                    onClick={() => updateRequest(request.id, "reject")}
                    className="inline-flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/5 px-4 py-2.5 text-sm font-semibold text-red-300 transition hover:bg-red-500/10"
                  >
                    <X size={16} />
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export default Dashboard;