import { useState } from "react";
import { defaultSessionState, normalizeSessionState, SessionState, SessionStatus } from "../types/session";

interface TradingControlsProps {
  status: SessionStatus;
  onStatusChange: (status: SessionStatus, patch?: Partial<SessionState>) => void;
  onError?: (message: string | null) => void;
}

const API_URL =
  (import.meta.env.VITE_API_URL as string | undefined) ||
  (import.meta.env.VITE_API_BASE as string | undefined) ||
  "http://localhost:8000";

const START_PAYLOAD = {
  strategy: "murphy_candles_v1",
  instrument: "EUR_USD",
  granularity: "M5",
  risk: 0.5,
  max_positions: 1,
};

export function TradingControls({ status, onStatusChange, onError }: TradingControlsProps) {
  const [action, setAction] = useState<"start" | "stop" | null>(null);

  const isRunning = status === "running";
  const startDisabled = isRunning || action !== null;
  const stopDisabled = (!isRunning && status !== "error") || action !== null;

  const handleStart = async () => {
    setAction("start");
    onError?.(null);
    try {
      const response = await fetch(`${API_URL}/api/session/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(START_PAYLOAD),
      });
      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || "Failed to start session");
      }
      const payload = (await response.json()) as { status: string; run_id?: string };
      const snapshot = normalizeSessionState({
        ...defaultSessionState,
        status: "running",
        run_id: payload.run_id ?? null,
        timestamp: new Date().toISOString(),
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
        run_id: payload.run_id ?? null,
        timestamp: new Date().toISOString(),
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
