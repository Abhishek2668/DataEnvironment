import { useCallback, useEffect, useState } from "react";
import LiveMetrics from "../components/LiveMetrics";
import TradingControls from "../components/TradingControls";
import {
  defaultSessionState,
  normalizeSessionState,
  SessionState,
  SessionStatus,
} from "../types/session";

const API_URL =
  (import.meta.env.VITE_API_URL as string | undefined) ||
  (import.meta.env.VITE_API_BASE as string | undefined) ||
  "http://localhost:8000";

export default function Dashboard() {
  const [session, setSession] = useState<SessionState>(defaultSessionState);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const fetchSessionState = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_URL}/api/session/state`);
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || "Failed to load session state");
      }
      const data = await response.json();
      const snapshot = normalizeSessionState(data);
      setSession(snapshot);
      setLoadError(null);
    } catch (error) {
      console.error("Failed to load session state", error);
      setLoadError("Unable to load the trading session. The backend may be offline.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchSessionState();
  }, [fetchSessionState]);

  const handleStatusChange = (status: SessionStatus, patch?: Partial<SessionState>) => {
    setSession((prev) => normalizeSessionState({ ...prev, ...patch, status }));
  };

  const handleSessionUpdate = (next: SessionState) => {
    setSession(next);
  };

  return (
    <div className="min-h-screen bg-gray-950 px-4 py-8 text-white sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <header className="space-y-2">
          <h1 className="text-3xl font-bold">Forex Trading Dashboard</h1>
          <p className="text-sm text-gray-400">
            Monitor the autonomous trading session, view live performance, and control the trading engine.
          </p>
        </header>

        {loadError && (
          <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            {loadError}
          </div>
        )}

        {loading ? (
          <div className="rounded-xl bg-gray-900 p-6 text-sm text-gray-400">Loading session state…</div>
        ) : (
          <div className="space-y-6">
            <div className="rounded-xl bg-gray-900 p-6 shadow-lg">
              <TradingControls
                status={session.status}
                onStatusChange={(nextStatus, patch) => {
                  handleStatusChange(nextStatus, patch);
                  setActionError(null);
                }}
                onError={setActionError}
              />
              <div className="mt-4 text-sm text-gray-400">
                Current Status: {" "}
                <span className="font-semibold text-white">
                  {session.status.charAt(0).toUpperCase() + session.status.slice(1)}
                </span>
                {session.run_id && <span className="ml-2 text-gray-500">· Run ID {session.run_id}</span>}
              </div>
              {session.message && (
                <p className="mt-2 text-sm text-amber-200">{session.message}</p>
              )}
              {actionError && <p className="mt-3 text-sm text-red-300">{actionError}</p>}
            </div>

            <LiveMetrics session={session} onSessionUpdate={handleSessionUpdate} />
          </div>
        )}
      </div>
    </div>
  );
}
