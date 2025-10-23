import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { Button } from "./components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./components/ui/card";
import { Input } from "./components/ui/input";
import { Select } from "./components/ui/select";
import { useApi } from "./hooks/useApi";
import { useEventStream } from "./hooks/useEventStream";
import { api } from "./lib/api";

const DASHBOARD_TZ = "America/Winnipeg";

const formatMetricValue = (value: unknown) => {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    if (Math.abs(value) >= 1000) {
      return value.toFixed(0);
    }
    return value.toFixed(2);
  }
  return String(value);
};

interface StrategyDefinition {
  name: string;
  params: { name: string; type: string; default: unknown }[];
}

interface RunSummary {
  id: string;
  type: string;
  status: string;
  strategy: string;
  instrument: string;
  granularity: string;
  started_at: string;
  ended_at?: string | null;
  config: Record<string, unknown>;
}

interface MetricsPayload {
  metrics: Record<string, number | string>;
  equity_curve: { time: string; equity: number }[];
}

interface AccountSnapshot {
  balance?: number;
  equity?: number;
  marginAvailable?: number;
  [key: string]: unknown;
}

interface PriceTick {
  instrument: string;
  mid: number;
  bid: number;
  ask: number;
  time: string;
}

interface LogEntry {
  event?: string;
  [key: string]: unknown;
}

export default function App() {
  const { data: config } = useApi<{ base_currency: string; timezone: string; broker: string; environment: string }>(
    "/api/config"
  );
  const {
    data: account,
    refetch: refreshAccount,
  } = useApi<AccountSnapshot>("/api/account", { immediate: true });
  const { data: orders, refetch: refreshOrders } = useApi<Record<string, unknown>[]>("/api/orders");
  const { data: positions, refetch: refreshPositions } = useApi<Record<string, unknown>[]>("/api/positions");
  const { data: strategies } = useApi<StrategyDefinition[]>("/api/strategies");
  const { data: runs, refetch: refreshRuns } = useApi<RunSummary[]>("/api/runs");

  const [selectedStrategy, setSelectedStrategy] = useState("sma");
  const [instrument, setInstrument] = useState("EUR_USD");
  const [granularity, setGranularity] = useState("M5");
  const [risk, setRisk] = useState(0.5);
  const [stopDistance, setStopDistance] = useState(20);
  const [takeProfit, setTakeProfit] = useState<number | undefined>();
  const [spreadPips, setSpreadPips] = useState(0.8);
  const [maxPositions, setMaxPositions] = useState(1);
  const [strategyParams, setStrategyParams] = useState<Record<string, string | number>>({});

  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [priceInstrument, setPriceInstrument] = useState("EUR_USD");
  const [prices, setPrices] = useState<PriceTick[]>([]);
  const [metrics, setMetrics] = useState<MetricsPayload | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [backtestStatus, setBacktestStatus] = useState<string | null>(null);
  const [liveStatus, setLiveStatus] = useState<string | null>(null);
  const [logsPaused, setLogsPaused] = useState(false);

  const strategyDefinition = useMemo(() => {
    return strategies?.find((item) => item.name === selectedStrategy);
  }, [strategies, selectedStrategy]);

  useEffect(() => {
    if (strategies && strategies.length > 0) {
      const exists = strategies.some((strategy) => strategy.name === selectedStrategy);
      if (!exists) {
        setSelectedStrategy(strategies[0].name);
      }
    }
  }, [strategies, selectedStrategy]);

  const parsedStrategyParams = useMemo(() => {
    if (!strategyDefinition) {
      return strategyParams;
    }
    const result: Record<string, unknown> = {};
    for (const param of strategyDefinition.params) {
      const raw = strategyParams[param.name];
      if (raw === undefined || raw === "") continue;
      if (param.type === "int" || param.type === "float" || param.type === "float | None" || param.type === "float | NoneType") {
        const numeric = Number(raw);
        if (!Number.isNaN(numeric)) {
          result[param.name] = numeric;
          continue;
        }
      }
      result[param.name] = raw;
    }
    return result;
  }, [strategyDefinition, strategyParams]);

  useEffect(() => {
    if (strategyDefinition) {
      const defaults: Record<string, string | number> = {};
      for (const param of strategyDefinition.params) {
        defaults[param.name] = typeof param.default === "number" || typeof param.default === "string" ? param.default : "";
      }
      setStrategyParams(defaults);
    }
  }, [strategyDefinition]);

  const handleLog = useCallback(
    (entry: LogEntry) => {
      if (!logsPaused) {
        setLogs((prev) => [entry, ...prev].slice(0, 200));
      }
      if (entry.event && ["live_complete", "live_error", "live_stopped"].includes(entry.event as string)) {
        void refreshRuns();
        void refreshAccount();
        void refreshOrders();
        void refreshPositions();
      }
    },
    [logsPaused, refreshAccount, refreshOrders, refreshPositions, refreshRuns]
  );

  const handlePrice = useCallback((tick: PriceTick) => {
    setPrices((prev) => {
      const next = [tick, ...prev.filter((item) => item.instrument !== tick.instrument || item.time !== tick.time)];
      return next.slice(0, 200);
    });
  }, []);

  const handleEvent = useCallback(() => {
    void refreshOrders();
    void refreshPositions();
    void refreshAccount();
  }, [refreshAccount, refreshOrders, refreshPositions]);

  useEventStream<LogEntry>("/api/stream/logs", handleLog);
  useEventStream<PriceTick>(`/api/stream/prices?instrument=${priceInstrument}`, handlePrice);
  useEventStream<Record<string, unknown>>("/api/stream/events", handleEvent);

  useEffect(() => {
    if (runs && runs.length > 0 && !selectedRunId) {
      setSelectedRunId(runs[0].id);
    }
  }, [runs, selectedRunId]);

  useEffect(() => {
    const fetchMetrics = async () => {
      if (!selectedRunId) {
        setMetrics(null);
        return;
      }
      try {
        const payload = await api<MetricsPayload>(`/api/runs/${selectedRunId}/metrics`);
        setMetrics(payload);
      } catch (error) {
        console.error(error);
        setMetrics(null);
      }
    };
    void fetchMetrics();
  }, [selectedRunId]);

  const equityData = useMemo(() => {
    if (!metrics?.equity_curve) {
      return [];
    }
    return metrics.equity_curve.map((point) => ({
      ...point,
      time: new Date(point.time).toLocaleTimeString("en-CA", { timeZone: DASHBOARD_TZ }),
    }));
  }, [metrics]);

  const runLive = async () => {
    try {
      setLiveStatus("Starting live session...");
      await api("/api/run-live", {
        method: "POST",
        body: JSON.stringify({
          strategy: selectedStrategy,
          instrument,
          granularity,
          risk,
          sl: stopDistance,
          tp: takeProfit,
          spread_pips: spreadPips,
          max_positions: maxPositions,
          params: parsedStrategyParams,
        }),
      });
      setLiveStatus("Live session started");
      void refreshRuns();
    } catch (error) {
      console.error(error);
      setLiveStatus((error as Error).message);
    }
  };

  const stopLive = async () => {
    try {
      setLiveStatus("Stopping live session...");
      await api("/api/stop-live", { method: "POST" });
      setLiveStatus("Live session stopped");
      void refreshRuns();
    } catch (error) {
      console.error(error);
      setLiveStatus((error as Error).message);
    }
  };

  const runBacktest = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());
    try {
      setBacktestStatus("Running backtest...");
      const response = await api<MetricsPayload & { run_id: string }>("/api/backtest", {
        method: "POST",
        body: JSON.stringify({
          strategy: payload.strategy,
          instrument: payload.instrument,
          granularity: payload.granularity,
          risk: Number(payload.risk),
          spread_pips: Number(payload.spread_pips),
          slippage: Number(payload.slippage),
          max_positions: Number(payload.max_positions),
          from: payload.from || null,
          to: payload.to || null,
          params: parsedStrategyParams,
        }),
      });
      setMetrics({ metrics: response.metrics, equity_curve: response.equity_curve });
      setSelectedRunId(response.run_id);
      setBacktestStatus("Backtest complete");
      void refreshRuns();
    } catch (error) {
      console.error(error);
      setBacktestStatus((error as Error).message);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 pb-20 text-white">
      <header className="border-b border-zinc-800 bg-neutral-950/60 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-6 py-6 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-bold">Forex Paper Trading Dashboard</h1>
            <p className="text-sm text-zinc-400">
              Base currency: {config?.base_currency ?? "—"} · Timezone: {config?.timezone ?? DASHBOARD_TZ}
            </p>
          </div>
          <div className="flex gap-3">
            <Button variant="outline" onClick={stopLive}>
              Stop Live
            </Button>
            <Button onClick={runLive}>Start Live</Button>
          </div>
        </div>
      </header>

      <main className="mx-auto mt-8 flex max-w-6xl flex-col gap-6 px-6">
        <section className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle>Balance</CardTitle>
              <span className="text-sm text-zinc-400">{config?.base_currency ?? "USD"}</span>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-semibold">
                {account?.balance ? account.balance.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "—"}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Equity</CardTitle>
              <span className="text-sm text-zinc-400">Live marked-to-market</span>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-semibold">
                {account?.equity ? account.equity.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "—"}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Live Status</CardTitle>
              <span className="text-sm text-zinc-400">Paper trading only</span>
            </CardHeader>
            <CardContent>
              <div className="text-sm text-zinc-300">{liveStatus ?? "Idle"}</div>
            </CardContent>
          </Card>
        </section>

        <section className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Equity Curve</CardTitle>
              <span className="text-sm text-zinc-400">Latest run metrics</span>
            </CardHeader>
            <CardContent>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={equityData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                    <XAxis dataKey="time" stroke="#71717a" tick={{ fontSize: 12 }} hide={equityData.length > 40} />
                    <YAxis stroke="#71717a" tick={{ fontSize: 12 }} domain={['auto', 'auto']} />
                    <Tooltip contentStyle={{ backgroundColor: "#18181b", borderRadius: 12, border: "1px solid #27272a" }} />
                    <Line type="monotone" dataKey="equity" stroke="#22d3ee" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              {metrics?.metrics && (
                <div className="mt-6 grid gap-2 text-sm text-zinc-300 sm:grid-cols-2">
                  {Object.entries(metrics.metrics).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between rounded-xl bg-neutral-900 px-4 py-2">
                      <span className="text-xs uppercase tracking-wide text-zinc-500">{key.replace(/_/g, " ")}</span>
                      <span className="font-medium text-white">{formatMetricValue(value)}</span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Live Prices</CardTitle>
              <span className="text-sm text-zinc-400">Streaming mid prices</span>
            </CardHeader>
            <CardContent>
              <Select value={priceInstrument} onChange={(event) => setPriceInstrument(event.target.value)}>
                <option value="EUR_USD">EUR/USD</option>
                <option value="GBP_USD">GBP/USD</option>
                <option value="USD_JPY">USD/JPY</option>
                <option value="AUD_USD">AUD/USD</option>
              </Select>
              <div className="mt-4 h-56 space-y-2 overflow-y-auto text-sm">
                {prices.filter((tick) => tick.instrument === priceInstrument).slice(0, 30).map((tick) => (
                  <div key={tick.time} className="flex items-center justify-between rounded-lg bg-neutral-900 px-3 py-2">
                    <div>
                      <div className="font-medium">{tick.instrument}</div>
                      <div className="text-xs text-zinc-500">
                        {new Date(tick.time).toLocaleTimeString("en-CA", { timeZone: DASHBOARD_TZ })}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm text-sky-300">{tick.mid.toFixed(5)}</div>
                      <div className="text-xs text-zinc-500">Bid {tick.bid.toFixed(5)} · Ask {tick.ask.toFixed(5)}</div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Strategy Control</CardTitle>
              <span className="text-sm text-zinc-400">Configure live paper trading session</span>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4">
                <div className="grid gap-2">
                  <label className="text-sm text-zinc-300">Strategy</label>
                  <Select value={selectedStrategy} onChange={(event) => setSelectedStrategy(event.target.value)}>
                    {strategies?.map((strategy) => (
                      <option key={strategy.name} value={strategy.name}>
                        {strategy.name.toUpperCase()}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <label className="text-sm text-zinc-300">Instrument</label>
                    <Input value={instrument} onChange={(event) => setInstrument(event.target.value)} />
                  </div>
                  <div className="grid gap-2">
                    <label className="text-sm text-zinc-300">Granularity</label>
                    <Input value={granularity} onChange={(event) => setGranularity(event.target.value)} />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <label className="text-sm text-zinc-300">Risk %</label>
                    <Input type="number" step="0.1" value={risk} onChange={(event) => setRisk(Number(event.target.value))} />
                  </div>
                  <div className="grid gap-2">
                    <label className="text-sm text-zinc-300">Max Positions</label>
                    <Input
                      type="number"
                      value={maxPositions}
                      min={1}
                      onChange={(event) => setMaxPositions(Number(event.target.value))}
                    />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div className="grid gap-2">
                    <label className="text-sm text-zinc-300">Stop (pips)</label>
                    <Input
                      type="number"
                      value={stopDistance}
                      min={1}
                      onChange={(event) => setStopDistance(Number(event.target.value))}
                    />
                  </div>
                  <div className="grid gap-2">
                    <label className="text-sm text-zinc-300">Take Profit (pips)</label>
                    <Input
                      type="number"
                      value={takeProfit ?? ""}
                      onChange={(event) => setTakeProfit(event.target.value ? Number(event.target.value) : undefined)}
                    />
                  </div>
                  <div className="grid gap-2">
                    <label className="text-sm text-zinc-300">Spread (pips)</label>
                    <Input
                      type="number"
                      value={spreadPips}
                      min={0}
                      step="0.1"
                      onChange={(event) => setSpreadPips(Number(event.target.value))}
                    />
                  </div>
                </div>
                {strategyDefinition && strategyDefinition.params.length > 0 && (
                  <div className="grid gap-2">
                    <label className="text-sm text-zinc-300">Strategy Parameters</label>
                    <div className="grid gap-3 sm:grid-cols-2">
                      {strategyDefinition.params.map((param) => (
                        <div key={param.name} className="grid gap-1">
                          <span className="text-xs text-zinc-500">{param.name}</span>
                          <Input
                            value={strategyParams[param.name] ?? ""}
                            onChange={(event) =>
                              setStrategyParams((prev) => ({ ...prev, [param.name]: event.target.value }))
                            }
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <div className="flex items-center justify-between rounded-xl bg-neutral-900 px-4 py-3 text-sm text-zinc-400">
                  <span>Live status</span>
                  <span className="text-zinc-200">{liveStatus ?? "Ready"}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Backtest Runner</CardTitle>
              <span className="text-sm text-zinc-400">Replay stored candles for quick validation</span>
            </CardHeader>
            <CardContent>
              <form className="grid gap-4" onSubmit={runBacktest}>
                <input type="hidden" name="strategy" value={selectedStrategy} />
                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <label className="text-sm text-zinc-300">Instrument</label>
                    <Input name="instrument" defaultValue={instrument} required />
                  </div>
                  <div className="grid gap-2">
                    <label className="text-sm text-zinc-300">Granularity</label>
                    <Input name="granularity" defaultValue={granularity} required />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <label className="text-sm text-zinc-300">Risk %</label>
                    <Input name="risk" type="number" step="0.1" defaultValue={risk} required />
                  </div>
                  <div className="grid gap-2">
                    <label className="text-sm text-zinc-300">Max Positions</label>
                    <Input name="max_positions" type="number" defaultValue={maxPositions} min={1} required />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <label className="text-sm text-zinc-300">Spread (pips)</label>
                    <Input name="spread_pips" type="number" step="0.1" defaultValue={spreadPips} required />
                  </div>
                  <div className="grid gap-2">
                    <label className="text-sm text-zinc-300">Slippage</label>
                    <Input name="slippage" type="number" step="0.00001" defaultValue={0.00005} required />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <label className="text-sm text-zinc-300">From</label>
                    <Input name="from" type="datetime-local" />
                  </div>
                  <div className="grid gap-2">
                    <label className="text-sm text-zinc-300">To</label>
                    <Input name="to" type="datetime-local" />
                  </div>
                </div>
                <Button type="submit">Run Backtest</Button>
                {backtestStatus && <p className="text-sm text-zinc-400">{backtestStatus}</p>}
              </form>
            </CardContent>
          </Card>
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Open Positions</CardTitle>
              <Button variant="ghost" size="sm" onClick={() => void refreshPositions()}>
                Refresh
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                {positions && positions.length > 0 ? (
                  positions.map((position, index) => (
                    <div key={index} className="rounded-xl bg-neutral-900 px-4 py-3">
                      <pre className="whitespace-pre-wrap text-xs text-zinc-300">
                        {JSON.stringify(position, null, 2)}
                      </pre>
                    </div>
                  ))
                ) : (
                  <div className="rounded-xl bg-neutral-900 px-4 py-3 text-zinc-500">No open positions</div>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Orders</CardTitle>
              <Button variant="ghost" size="sm" onClick={() => void refreshOrders()}>
                Refresh
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                {orders && orders.length > 0 ? (
                  orders.map((order, index) => (
                    <div key={index} className="rounded-xl bg-neutral-900 px-4 py-3">
                      <pre className="whitespace-pre-wrap text-xs text-zinc-300">{JSON.stringify(order, null, 2)}</pre>
                    </div>
                  ))
                ) : (
                  <div className="rounded-xl bg-neutral-900 px-4 py-3 text-zinc-500">No orders</div>
                )}
              </div>
            </CardContent>
          </Card>
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Runs</CardTitle>
              <span className="text-sm text-zinc-400">Recent backtests and live sessions</span>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                {runs?.map((run) => (
                  <button
                    key={run.id}
                    onClick={() => setSelectedRunId(run.id)}
                    className={`w-full rounded-xl border px-4 py-3 text-left transition ${
                      selectedRunId === run.id ? "border-sky-500 bg-sky-500/10" : "border-zinc-800 bg-neutral-900 hover:border-sky-500"
                    }`}
                  >
                    <div className="flex items-center justify-between text-sm font-semibold text-white">
                      <span>
                        {run.strategy.toUpperCase()} · {run.instrument}
                      </span>
                      <span className="text-xs uppercase text-zinc-400">{run.status}</span>
                    </div>
                    <div className="text-xs text-zinc-500">
                      {new Date(run.started_at).toLocaleString("en-CA", { timeZone: DASHBOARD_TZ })}
                    </div>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Logs</CardTitle>
                  <span className="text-sm text-zinc-400">Latest 200 events</span>
                </div>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" onClick={() => setLogsPaused((value) => !value)}>
                    {logsPaused ? "Resume" : "Pause"}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setLogs([])}>
                    Clear
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="h-72 space-y-2 overflow-y-auto rounded-xl bg-neutral-900 px-4 py-3 text-xs text-zinc-300">
                {logs.map((log, index) => (
                  <div key={index} className="rounded-lg bg-neutral-950/60 px-3 py-2">
                    {JSON.stringify(log)}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </section>
      </main>
    </div>
  );
}
