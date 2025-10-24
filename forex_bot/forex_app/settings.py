"""Application settings module."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, PositiveFloat, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration values for the trading platform."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        frozen=True,
    )

    BROKER: Literal["oanda", "paper"] = "paper"
    OANDA_ENV: Literal["practice"] = "practice"
    OANDA_API_TOKEN: SecretStr | None = None
    OANDA_ACCOUNT_ID: str | None = None

    BASE_CURRENCY: str = "CAD"
    DEFAULT_TIMEZONE: str = "America/Winnipeg"

    ENABLE_PROMETHEUS: bool = True
    DASH_TOKEN: str = "dev-token"

    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # Trading controls
    TRADE_ALLOCATION_PCT: PositiveFloat = Field(default=0.02, gt=0.0)  # type: ignore[assignment]
    RISK_PCT_PER_TRADE: PositiveFloat = Field(default=0.5, gt=0.0)  # type: ignore[assignment]
    MAX_LEVERAGE: PositiveFloat = Field(default=20.0, gt=0.0)  # type: ignore[assignment]
    MAX_DRAWDOWN_STOP: PositiveFloat = Field(default=0.2, gt=0.0)  # type: ignore[assignment]
    MIN_SIGNAL_CONF: PositiveFloat = Field(default=0.6, gt=0.0)  # type: ignore[assignment]
    USE_RL_SIGNALS: bool = True
    USE_NEWS_FILTER: bool = True

    NEWS_PROVIDER: Literal["gdelt", "alphavantage"] = "gdelt"
    GDELT_BASE: str = "https://api.gdeltproject.org/api/v2/doc/doc"
    ALPHAVANTAGE_API_KEY: SecretStr | None = None

    DATA_DIR: Path = Path("data")
    DB_PATH: Path = Path("data/trading.db")
    MODEL_PATH: Path = Path("data/models/ppo_fx.zip")

    HEARTBEAT_INTERVAL_SECONDS: PositiveFloat = PositiveFloat(5.0)  # type: ignore[arg-type]

class SettingsUpdate(BaseModel):
    """Partial update payload for mutable settings exposed over the API."""

    TRADE_ALLOCATION_PCT: float | None = Field(default=None, ge=0.0, le=1.0)
    RISK_PCT_PER_TRADE: float | None = Field(default=None, ge=0.0, le=1.0)
    MAX_LEVERAGE: float | None = Field(default=None, gt=0.0)
    MAX_DRAWDOWN_STOP: float | None = Field(default=None, ge=0.0, le=1.0)
    MIN_SIGNAL_CONF: float | None = Field(default=None, ge=0.0, le=1.0)
    USE_RL_SIGNALS: bool | None = None
    USE_NEWS_FILTER: bool | None = None
    CORS_ORIGINS: list[str] | None = None


@lru_cache
def _load_settings() -> Settings:
    settings = Settings()
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return settings


def get_settings(*, reload: bool = False) -> Settings:
    """Return cached settings instance."""

    if reload:
        _load_settings.cache_clear()
    return _load_settings()


def update_settings(settings: Settings, patch: SettingsUpdate) -> Settings:
    """Return a new Settings instance with the provided patch applied."""

    data = settings.model_dump()
    updates = patch.model_dump(exclude_none=True)
    data.update(updates)
    _load_settings.cache_clear()
    return Settings(**data)


__all__ = ["Settings", "SettingsUpdate", "get_settings", "update_settings"]
