from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer

from forex.backtest.engine import BacktestConfig, Backtester, CandleBar
from forex.backtest.reports import write_reports
from forex.broker.oanda import OandaBroker
from forex.broker.paper_sim import PaperSimBroker
from forex.config import Settings, get_settings
from forex.data.candles_store import CandleStore
from forex.data.models import Candle
from forex.logging_config import configure_logging, get_logger
from forex.strategy.rsi_mean_revert import RSIMeanRevertStrategy
from forex.strategy.sma_crossover import SMACrossoverStrategy

app = typer.Typer(help="Forex paper trading CLI")
logger = get_logger(__name__)


def load_strategy(name: str):
    name = name.lower()
    if name == "sma":
        return SMACrossoverStrategy()
    if name == "rsi":
        return RSIMeanRevertStrategy()
    raise typer.BadParameter(f"Unknown strategy {name}")


def load_broker(settings: Settings):
    if settings.broker == "oanda":
        return OandaBroker()
    return PaperSimBroker(spread_pips=settings.spread_pips_default)


@app.callback()
def main(
    ctx: typer.Context,
    config: Annotated[Path, typer.Option(".env", help="Config file path")] = Path(".env"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    configure_logging(debug)
    if config.exists():
        ctx.obj = Settings(_env_file=str(config))
    else:
        ctx.obj = get_settings()


@app.command("run-live")
def run_live(
    ctx: typer.Context,
    strategy: str = typer.Option(...),
    instrument: str = typer.Option(...),
    granularity: str = typer.Option("M1"),
    risk: float = typer.Option(0.5),
    max_trades: int = typer.Option(1),
) -> None:
    settings: Settings = ctx.obj or get_settings()
    broker = load_broker(settings)
    strat = load_strategy(strategy)

    async def _run() -> None:
        account = await broker.get_account()
        logger.info("account", extra=account)
        async for price in broker.price_stream([instrument]):
            strat.on_price_tick(price)
            strat.on_bar_close(price)
            signal = getattr(strat, "get_signal", lambda: None)()
            if signal:
                logger.info("signal", extra={"side": signal.side, "reason": signal.reason})

    asyncio.run(_run())


@app.command()
def backtest(
    ctx: typer.Context,
    strategy: str = typer.Option(...),
    instrument: str = typer.Option(...),
    granularity: str = typer.Option("M5"),
    risk: float = typer.Option(0.5),
    max_trades: int = typer.Option(1),
    spread_pips: float = typer.Option(0.8),
    data_csv: Optional[Path] = typer.Option(None),
    output_dir: Path = typer.Option(Path("backtest_output")),
) -> None:
    settings: Settings = ctx.obj or get_settings()
    strat = load_strategy(strategy)
    config = BacktestConfig(
        instrument=instrument,
        granularity=granularity,
        risk_pct=risk,
        max_positions=max_trades,
        spread=spread_pips * 0.0001,
    )
    candles: list[CandleBar] = []
    if data_csv:
        import pandas as pd

        df = pd.read_csv(data_csv)
        for _, row in df.iterrows():
            candles.append(
                CandleBar(
                    time=datetime.fromisoformat(row["time"]),
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row.get("volume", 0),
                )
            )
    else:
        store = CandleStore()
        stored = store.load_candles(instrument, granularity)
        for candle in stored:
            candles.append(
                CandleBar(
                    time=candle.time,
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                )
            )
    if not candles:
        raise typer.BadParameter("No candles available for backtest")
    backtester = Backtester(strat, config)
    result = backtester.run(candles)
    write_reports(result, output_dir)
    typer.echo(json.dumps(result.metrics, indent=2, default=str))


@app.command("import-candles")
def import_candles(
    ctx: typer.Context,
    instrument: str = typer.Option(...),
    granularity: str = typer.Option("H1"),
    days: int = typer.Option(30),
    csv: Optional[Path] = typer.Option(None),
) -> None:
    settings: Settings = ctx.obj or get_settings()
    store = CandleStore()
    candles: list[Candle] = []
    if csv:
        import pandas as pd

        df = pd.read_csv(csv)
        for _, row in df.iterrows():
            candles.append(
                Candle(
                    instrument=instrument,
                    granularity=granularity,
                    time=datetime.fromisoformat(row["time"]),
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row.get("volume", 0),
                )
            )
    else:
        broker = load_broker(settings)
        data = asyncio.run(
            broker.get_candles(instrument=instrument, granularity=granularity, count=days * 24)
        )
        for item in data:
            candle = Candle(
                instrument=instrument,
                granularity=granularity,
                time=datetime.fromisoformat(item["time"].replace("Z", "+00:00")),
                open=float(item["mid"]["o"]),
                high=float(item["mid"]["h"]),
                low=float(item["mid"]["l"]),
                close=float(item["mid"]["c"]),
                volume=float(item.get("volume", 0)),
            )
            candles.append(candle)
    store.upsert_candles(candles)
    typer.echo(f"Imported {len(candles)} candles")


@app.command("show-metrics")
def show_metrics(run_id: str = typer.Option("last"), output_dir: Path = typer.Option(Path("backtest_output"))) -> None:
    metrics_path = output_dir / "metrics.json"
    if not metrics_path.exists():
        raise typer.BadParameter("No metrics found")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    typer.echo(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    app()
