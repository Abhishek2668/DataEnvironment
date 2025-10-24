export type SessionStatus = "running" | "stopped" | "error";

export interface SessionState {
  status: SessionStatus;
  running: boolean;
  run_id: string | null;
  instrument: string | null;
  timeframe: string | null;
  last_signal_direction: string | null;
  last_signal_confidence: number | null;
  open_trades: number;
  unrealized_pnl: number | null;
  last_candle_at: string | null;
  activity: string | null;
  message: string | null;
  confidence: number | null;
}

export const defaultSessionState: SessionState = {
  status: "stopped",
  running: false,
  run_id: null,
  instrument: null,
  timeframe: null,
  last_signal_direction: null,
  last_signal_confidence: null,
  open_trades: 0,
  unrealized_pnl: null,
  last_candle_at: null,
  activity: null,
  message: null,
  confidence: null,
};

export function normalizeSessionState(value: Partial<SessionState> | null | undefined): SessionState {
  const running = Boolean(value?.running ?? (value?.status === "running"));
  const status: SessionStatus = value?.status === "error" ? "error" : running ? "running" : "stopped";
  return {
    status,
    running,
    run_id: value?.run_id ?? null,
    instrument: value?.instrument ?? null,
    timeframe: value?.timeframe ?? null,
    last_signal_direction: value?.last_signal_direction ?? value?.last_signal ?? null,
    last_signal_confidence: value?.last_signal_confidence ?? value?.confidence ?? null,
    open_trades: value?.open_trades ?? value?.open_positions ?? 0,
    unrealized_pnl: value?.unrealized_pnl ?? null,
    last_candle_at: value?.last_candle_at ?? value?.last_candle_timestamp ?? ("timestamp" in (value ?? {}) ? (value as any).timestamp ?? null : null),
    activity: value?.activity ?? null,
    message: value?.message ?? null,
    confidence: value?.confidence ?? value?.last_signal_confidence ?? null,
  };
}
