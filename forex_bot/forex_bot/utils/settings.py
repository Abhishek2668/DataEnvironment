"""Application configuration management."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the trading backend."""

    # --- Pydantic v2 model config ---
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # <-- this ignores unknown fields in .env
    )

    # --- Core trading configuration ---
    db_path: Path = Field(default=Path("data/trading.db"), alias="DB_PATH")
    broker: str = Field(default="paper", alias="BROKER")
    base_currency: str = Field(default="USD", alias="BASE_CURRENCY")
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:5173"], alias="CORS_ORIGINS")
    loop_interval_seconds: float = Field(default=5.0, alias="LOOP_INTERVAL_SECONDS")
    candle_interval_seconds: int = Field(default=60, alias="CANDLE_INTERVAL_SECONDS")
    paper_starting_balance: float = Field(default=100_000.0, alias="PAPER_STARTING_BALANCE")
    trade_units: int = Field(default=1_000, alias="TRADE_UNITS")
    take_profit_pct: float = Field(default=0.0015, alias="TAKE_PROFIT_PCT")
    stop_loss_pct: float = Field(default=0.0008, alias="STOP_LOSS_PCT")
    signal_confidence_threshold: float = Field(default=0.6, alias="SIGNAL_CONFIDENCE_THRESHOLD")

    # --- OANDA settings ---
    oanda_env: str = Field(default="practice", alias="OANDA_ENV")
    oanda_api_token: Optional[SecretStr] = Field(default=None, alias="OANDA_API_TOKEN")
    oanda_account_id: Optional[str] = Field(default=None, alias="OANDA_ACCOUNT_ID")

    # --- Defaults ---
    default_instrument: str = Field(default="EUR_USD", alias="DEFAULT_INSTRUMENT")
    default_timeframe: str = Field(default="M5", alias="DEFAULT_TIMEFRAME")

    # --- Optional extra settings (ignored if not in .env) ---
    default_timezone: Optional[str] = Field(default="America/Winnipeg", alias="DEFAULT_TIMEZONE")
    enable_prometheus: Optional[bool] = Field(default=False, alias="ENABLE_PROMETHEUS")
    dash_token: Optional[str] = Field(default=None, alias="DASH_TOKEN")
    api_host: Optional[str] = Field(default="0.0.0.0", alias="API_HOST")
    api_port: Optional[int] = Field(default=8000, alias="API_PORT")
    data_dir: Optional[str] = Field(default="data", alias="DATA_DIR")
    trade_allocation_pct: Optional[float] = Field(default=0.02, alias="TRADE_ALLOCATION_PCT")
    risk_pct_per_trade: Optional[float] = Field(default=0.5, alias="RISK_PCT_PER_TRADE")
    max_leverage: Optional[float] = Field(default=20.0, alias="MAX_LEVERAGE")
    max_drawdown_stop: Optional[float] = Field(default=0.2, alias="MAX_DRAWDOWN_STOP")
    min_signal_conf: Optional[float] = Field(default=0.6, alias="MIN_SIGNAL_CONF")
    use_rl_signals: Optional[bool] = Field(default=False, alias="USE_RL_SIGNALS")
    use_news_filter: Optional[bool] = Field(default=False, alias="USE_NEWS_FILTER")

    def ensure_paths(self) -> None:
        """Ensure directories referenced by the settings exist."""
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""
    settings = Settings()
    settings.ensure_paths()
    return settings


__all__ = ["Settings", "get_settings"]
