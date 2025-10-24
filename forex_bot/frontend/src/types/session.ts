export type SessionStatus = "running" | "stopped" | "error";

export interface SessionState {
  status: SessionStatus;
  run_id: string | null;
  equity: number | null;
  start_equity: number | null;
  daily_return_pct: number | null;
  open_positions: number;
  trades_today: number;
  target_hit: boolean;
  loss_limit_hit: boolean;
  timestamp: string | null;
  message: string | null;
  strategy: string | null;
  instrument: string | null;
  granularity: string | null;
}

export const defaultSessionState: SessionState = {
  status: "stopped",
  run_id: null,
  equity: null,
  start_equity: null,
  daily_return_pct: null,
  open_positions: 0,
  trades_today: 0,
  target_hit: false,
  loss_limit_hit: false,
  timestamp: null,
  message: null,
  strategy: null,
  instrument: null,
  granularity: null,
};

export function normalizeSessionState(value: Partial<SessionState> | null | undefined): SessionState {
  const status: SessionStatus = value?.status === "running" || value?.status === "error" ? value.status : "stopped";
  return {
    status,
    run_id: value?.run_id ?? null,
    equity: value?.equity ?? null,
    start_equity: value?.start_equity ?? null,
    daily_return_pct: value?.daily_return_pct ?? null,
    open_positions: value?.open_positions ?? 0,
    trades_today: value?.trades_today ?? 0,
    target_hit: value?.target_hit ?? false,
    loss_limit_hit: value?.loss_limit_hit ?? false,
    timestamp: value?.timestamp ?? null,
    message: value?.message ?? null,
    strategy: value?.strategy ?? null,
    instrument: value?.instrument ?? null,
    granularity: value?.granularity ?? null,
  };
}
