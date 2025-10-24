"""Application configuration management."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime configuration for the trading backend."""

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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

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
