import { useEffect, useMemo, useRef, useState } from "react";
import { normalizeSessionState, SessionState } from "../types/session";
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

function formatNumber(value: number | null, options?: Intl.NumberFormatOptions) {
  if (value === null || Number.isNaN(value)) {
    return "--";
  }
  return value.toLocaleString(undefined, options);
}

function formatPercent(value: number | null) {
  if (value === null || Number.isNaN(value)) {
    return "--";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function formatTimestamp(value: string | null) {
  if (!value) return "--";
  try {
    const date = new Date(value);
    return `${date.toLocaleTimeString()} · ${date.toLocaleDateString()}`;
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
        case "engine.status":
        case "engine.state":
        case "engine.tick":
        case "trade.executed":
        case "candle.new":
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

  const directionAccent = useMemo(() => {
    if (metrics.last_signal_direction === "long") {
      return "text-emerald-400";
    }
    if (metrics.last_signal_direction === "short") {
      return "text-rose-400";
    }
    return "text-gray-400";
  }, [metrics.last_signal_direction]);

  const pnlAccent = useMemo(() => {
    if (metrics.unrealized_pnl === null) {
      return "text-gray-300";
    }
    if (metrics.unrealized_pnl > 0) {
      return "text-emerald-400";
    }
    if (metrics.unrealized_pnl < 0) {
      return "text-rose-400";
    }
    return "text-gray-300";
  }, [metrics.unrealized_pnl]);

  const cardMetrics = useMemo(
    () => [
      {
        label: "Open Trades",
        value: metrics.open_trades,
        format: (value: number | null) => formatNumber(value, { maximumFractionDigits: 0 }),
        accent: "bg-emerald-500/10 text-emerald-300",
      },
      {
        label: "Unrealized PnL",
        value: metrics.unrealized_pnl,
        format: (value: number | null) => `$${formatNumber(value, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
        accent: pnlAccent === "text-emerald-400" ? "bg-emerald-500/10 text-emerald-300" : pnlAccent === "text-rose-400" ? "bg-rose-500/10 text-rose-300" : "bg-slate-500/10 text-slate-200",
      },
      {
        label: "Signal Confidence",
        value: metrics.last_signal_confidence,
        format: (value: number | null) => formatPercent(value),
        accent: "bg-cyan-500/10 text-cyan-300",
      },
      {
        label: "Loop Activity",
        value: metrics.activity,
        format: (value: string | null) => (value ? value.toUpperCase() : "--"),
        accent: "bg-purple-500/10 text-purple-300",
      },
    ],
    [metrics.open_trades, metrics.unrealized_pnl, metrics.last_signal_confidence, metrics.activity, pnlAccent]
  );

  return (
    <div className="rounded-2xl border border-white/5 bg-gradient-to-br from-gray-900 via-slate-900 to-gray-950 p-6 text-white shadow-2xl">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-1">
          <p className="text-xs uppercase tracking-[0.35em] text-gray-400">Live Engine Feed</p>
          <h2 className="text-2xl font-semibold">{metrics.instrument ?? "--"}</h2>
          <p className="text-sm text-gray-400">
            Timeframe {metrics.timeframe ?? "--"} · Run {metrics.run_id ?? "--"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${
              connectionStatus === "open"
                ? "bg-emerald-500/10 text-emerald-300"
                : connectionStatus === "error"
                ? "bg-amber-500/10 text-amber-300"
                : "bg-gray-700/40 text-gray-300"
            }`}
          >
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-current" />
            {connectionStatus === "open" ? "Streaming" : connectionStatus === "error" ? "Reconnecting" : "Connecting"}
          </span>
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold ${
              metrics.running ? "bg-emerald-500/10 text-emerald-300" : "bg-slate-700/40 text-slate-200"
            }`}
          >
            {metrics.status === "running" ? "Engine Running" : metrics.status === "error" ? "Engine Error" : "Engine Idle"}
          </span>
        </div>
      </div>

      {connectionMessage && <p className="mt-4 text-sm text-amber-300">{connectionMessage}</p>}
      {metrics.message && metrics.status === "error" && (
        <p className="mt-4 text-sm text-rose-300">{metrics.message}</p>
      )}

      <div className="mt-6 grid gap-4 lg:grid-cols-5">
        <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-slate-900 via-slate-900 to-gray-900 p-5 shadow-lg lg:col-span-2">
          <div className="absolute -right-10 -top-10 h-24 w-24 rounded-full bg-emerald-500/10 blur-2xl" />
          <p className="text-xs uppercase tracking-wide text-gray-400">Latest Signal</p>
          <div className="mt-3 flex items-end gap-3">
            <span className={`text-4xl font-semibold ${directionAccent}`}>
              {metrics.last_signal_direction ? metrics.last_signal_direction.toUpperCase() : "--"}
            </span>
            <span className="text-sm text-gray-400">{formatPercent(metrics.last_signal_confidence)}</span>
          </div>
          <p className="mt-3 text-sm text-gray-300">Updated {formatTimestamp(metrics.last_candle_at)}</p>
        </div>
        {cardMetrics.map((item) => (
          <div key={item.label} className={`rounded-xl p-5 shadow-lg ${item.accent}`}>
            <p className="text-xs uppercase tracking-wide text-white/70">{item.label}</p>
            <p className="mt-3 text-2xl font-semibold text-white">{item.format(item.value)}</p>
          </div>
        ))}
      </div>

      <div className="mt-6 grid gap-3 text-sm text-gray-300 sm:grid-cols-2">
        <div className="rounded-lg bg-gray-950/50 p-4">
          <p className="text-xs uppercase tracking-wide text-gray-500">Last Candle</p>
          <p className="mt-2 font-medium">{formatTimestamp(metrics.last_candle_at)}</p>
        </div>
        <div className="rounded-lg bg-gray-950/50 p-4">
          <p className="text-xs uppercase tracking-wide text-gray-500">Loop Activity</p>
          <p className="mt-2 font-medium">{metrics.activity ? metrics.activity.toUpperCase() : "--"}</p>
        </div>
      </div>
    </div>
  );
}

export default LiveMetrics;
