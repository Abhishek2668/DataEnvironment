import { useEffect, useMemo, useRef, useState } from "react";
import { normalizeSessionState, SessionState, SessionStatus } from "../types/session";
import { subscribeSSE } from "../lib/sse";

interface LiveMetricsProps {
  session: SessionState;
  onSessionUpdate: (next: SessionState) => void;
}

interface SessionEventPayload extends Partial<SessionState> {
  type: string;
  trade?: Record<string, unknown>;
  [key: string]: unknown;
}

const STATUS_LABEL: Record<SessionStatus, string> = {
  running: "Running",
  stopped: "Stopped",
  error: "Error",
};

function formatNumber(value: number | null, options?: Intl.NumberFormatOptions) {
  if (value === null || Number.isNaN(value)) {
    return "--";
  }
  return value.toLocaleString(undefined, options);
}

function formatTimestamp(value: string | null) {
  if (!value) return "--";
  try {
    return new Date(value).toLocaleTimeString();
  } catch (error) {
    return value;
  }
}

export function LiveMetrics({ session, onSessionUpdate }: LiveMetricsProps) {
  const [metrics, setMetrics] = useState<SessionState>(session);
  const [connectionStatus, setConnectionStatus] = useState<"connecting" | "open" | "error">("connecting");
  const [connectionMessage, setConnectionMessage] = useState<string | null>(null);
  const metricsRef = useRef<SessionState>(session);

  useEffect(() => {
    setMetrics(session);
    metricsRef.current = session;
  }, [session]);

  useEffect(() => {
    const unsubscribe = subscribeSSE<SessionEventPayload>("/api/stream/events", (event) => {
      if (!event || typeof event !== "object") {
        return;
      }
      let mergedState: SessionState | null = null;
      setMetrics((prev) => {
        const merged = normalizeSessionState({ ...prev, ...event });
        metricsRef.current = merged;
        mergedState = merged;
        return merged;
      });
      const snapshot = mergedState ?? metricsRef.current;
      switch (event.type) {
        case "equity_update":
        case "session_started":
        case "session_stopped":
        case "target_hit":
        case "loss_limit_hit":
        case "new_trade":
          onSessionUpdate(snapshot);
          break;
        case "error":
          onSessionUpdate(snapshot);
          setConnectionMessage(event.message ? String(event.message) : "Session encountered an error.");
          break;
        default:
          break;
      }
    }, {
      onOpen: () => {
        setConnectionStatus("open");
        setConnectionMessage(null);
      },
      onError: () => {
        setConnectionStatus("error");
        setConnectionMessage("Connection lost. Attempting to reconnect...");
      },
    });

    return () => unsubscribe();
  }, [onSessionUpdate]);

  const cardMetrics = useMemo(
    () => [
      { label: "Equity", value: metrics.equity, format: (value: number | null) => `$${formatNumber(value, { maximumFractionDigits: 2 })}` },
      {
        label: "Daily Return",
        value: metrics.daily_return_pct,
        format: (value: number | null) => `${formatNumber(value, { maximumFractionDigits: 2 })}%`,
      },
      { label: "Open Positions", value: metrics.open_positions, format: (value: number | null) => formatNumber(value, { maximumFractionDigits: 0 }) },
      { label: "Trades Today", value: metrics.trades_today, format: (value: number | null) => formatNumber(value, { maximumFractionDigits: 0 }) },
      { label: "Target Hit", value: metrics.target_hit ? 1 : 0, format: () => (metrics.target_hit ? "Yes" : "No") },
      { label: "Loss Limit Hit", value: metrics.loss_limit_hit ? 1 : 0, format: () => (metrics.loss_limit_hit ? "Yes" : "No") },
    ],
    [metrics]
  );

  return (
    <div className="rounded-xl bg-gray-900 p-6 text-white shadow-lg">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold">Live Metrics</h2>
          <p className="text-sm text-gray-400">Real-time performance from the trading engine.</p>
        </div>
        <span
          className={`text-sm ${
            connectionStatus === "open"
              ? "text-emerald-400"
              : connectionStatus === "error"
              ? "text-amber-300"
              : "text-gray-300"
          }`}
        >
          {connectionStatus === "open" ? "Live" : connectionStatus === "error" ? "Reconnecting" : "Connecting"}
        </span>
      </div>

      {connectionMessage && <p className="mt-3 text-sm text-amber-300">{connectionMessage}</p>}
      {metrics.status === "error" && metrics.message && (
        <p className="mt-3 text-sm text-red-400">{metrics.message}</p>
      )}

      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {cardMetrics.map((item) => (
          <div key={item.label} className="rounded-lg bg-gray-950/60 p-4">
            <p className="text-xs uppercase tracking-wide text-gray-400">{item.label}</p>
            <p className="mt-2 text-lg font-semibold">{item.format(item.value)}</p>
          </div>
        ))}
      </div>

      <div className="mt-6 grid gap-3 text-sm text-gray-300 sm:grid-cols-2">
        <div className="rounded-lg bg-gray-950/60 p-4">
          <p className="text-xs uppercase tracking-wide text-gray-400">Run ID</p>
          <p className="mt-2 font-medium">{metrics.run_id ?? "--"}</p>
        </div>
        <div className="rounded-lg bg-gray-950/60 p-4">
          <p className="text-xs uppercase tracking-wide text-gray-400">Last Update</p>
          <p className="mt-2 font-medium">{formatTimestamp(metrics.timestamp)}</p>
        </div>
        <div className="rounded-lg bg-gray-950/60 p-4">
          <p className="text-xs uppercase tracking-wide text-gray-400">Strategy</p>
          <p className="mt-2 font-medium">{metrics.strategy ?? "--"}</p>
        </div>
        <div className="rounded-lg bg-gray-950/60 p-4">
          <p className="text-xs uppercase tracking-wide text-gray-400">Instrument</p>
          <p className="mt-2 font-medium">
            {metrics.instrument ?? "--"}
            {metrics.granularity ? ` · ${metrics.granularity}` : ""}
          </p>
        </div>
        <div className="rounded-lg bg-gray-950/60 p-4">
          <p className="text-xs uppercase tracking-wide text-gray-400">Session Status</p>
          <p className="mt-2 font-semibold text-white">{STATUS_LABEL[metrics.status]}</p>
        </div>
      </div>
    </div>
  );
}

export default LiveMetrics;
