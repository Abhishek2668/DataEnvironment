import { useEffect, useState } from "react";
import { defaultSessionState, normalizeSessionState, SessionState, SessionStatus } from "../types/session";

interface TradingControlsProps {
  session: SessionState;
  onStatusChange: (status: SessionStatus, patch?: Partial<SessionState>) => void;
  onError?: (message: string | null) => void;
}

const API_URL =
  (import.meta.env.VITE_API_URL as string | undefined) ||
  (import.meta.env.VITE_API_BASE as string | undefined) ||
  "http://localhost:8000";

const INSTRUMENTS = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CHF"];
const TIMEFRAMES = ["M1", "M5", "M15", "H1", "H4", "D"];

export function TradingControls({ session, onStatusChange, onError }: TradingControlsProps) {
  const status = session.status;
  const [action, setAction] = useState<"start" | "stop" | null>(null);
  const [instrument, setInstrument] = useState(session.instrument ?? "EUR_USD");
  const [timeframe, setTimeframe] = useState(session.timeframe ?? "M5");

  const isRunning = status === "running";
  const startDisabled = isRunning || action !== null;
  const stopDisabled = (!isRunning && status !== "error") || action !== null;

  useEffect(() => {
    if (session.instrument) {
      setInstrument(session.instrument);
    }
  }, [session.instrument]);

  useEffect(() => {
    if (session.timeframe) {
      setTimeframe(session.timeframe);
    }
  }, [session.timeframe]);

  const handleStart = async () => {
    setAction("start");
    onError?.(null);
    try {
      const response = await fetch(`${API_URL}/api/session/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instrument, timeframe }),
      });
      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || "Failed to start session");
      }
      const payload = (await response.json()) as { status: string; run_id?: string };
      const snapshot = normalizeSessionState({
        ...defaultSessionState,
        status: "running",
        running: true,
        run_id: payload.run_id ?? null,
        instrument,
        timeframe,
        activity: "idle",
      });
      onStatusChange(snapshot.status, snapshot);
    } catch (error) {
      console.error("Failed to start trading", error);
      onError?.("Unable to start trading session. Please try again.");
    } finally {
      setAction(null);
    }
  };

  const handleStop = async () => {
    setAction("stop");
    onError?.(null);
    try {
      const response = await fetch(`${API_URL}/api/session/stop`, { method: "POST" });
      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || "Failed to stop session");
      }
      const payload = (await response.json()) as { status: string; run_id?: string };
      const snapshot = normalizeSessionState({
        ...defaultSessionState,
        status: "stopped",
        running: false,
        run_id: payload.run_id ?? null,
      });
      onStatusChange(snapshot.status, snapshot);
    } catch (error) {
      console.error("Failed to stop trading", error);
      onError?.("Unable to stop trading session. Please try again.");
    } finally {
      setAction(null);
    }
  };

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 className="text-xl font-semibold">Trading Controls</h2>
        <p className="text-sm text-gray-400">Start or stop the autonomous trading engine.</p>
        <div className="mt-3 flex flex-wrap gap-3 text-sm text-gray-300">
          <label className="flex items-center gap-2 rounded-lg bg-gray-900/80 px-3 py-2 shadow-inner">
            <span className="text-xs uppercase tracking-wide text-gray-500">Instrument</span>
            <select
              value={instrument}
              onChange={(event) => setInstrument(event.target.value)}
              className="rounded-md border border-gray-700 bg-gray-950 px-2 py-1 text-sm text-white focus:border-emerald-500 focus:outline-none"
            >
              {INSTRUMENTS.map((value) => (
                <option key={value} value={value}>
                  {value.replace("_", "/")}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 rounded-lg bg-gray-900/80 px-3 py-2 shadow-inner">
            <span className="text-xs uppercase tracking-wide text-gray-500">Timeframe</span>
            <select
              value={timeframe}
              onChange={(event) => setTimeframe(event.target.value)}
              className="rounded-md border border-gray-700 bg-gray-950 px-2 py-1 text-sm text-white focus:border-emerald-500 focus:outline-none"
            >
              {TIMEFRAMES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={handleStart}
          disabled={startDisabled}
          className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-green-700 disabled:cursor-not-allowed disabled:bg-green-800/50"
        >
          {action === "start" ? "Starting..." : "Start Trading"}
        </button>
        <button
          type="button"
          onClick={handleStop}
          disabled={stopDisabled}
          className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-red-800/50"
        >
          {action === "stop" ? "Stopping..." : "Stop Trading"}
        </button>
      </div>
    </div>
  );
}

export default TradingControls;
