from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import pendulum
from pydantic import Field, PositiveFloat, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_TIMEZONE = "America/Winnipeg"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    broker: Literal["oanda", "paper"] = Field(default="oanda", alias="BROKER")
    oanda_env: Literal["practice"] = Field(default="practice", alias="OANDA_ENV")
    oanda_api_token: SecretStr | None = Field(default=None, alias="OANDA_API_TOKEN")
    oanda_account_id: str | None = Field(default=None, alias="OANDA_ACCOUNT_ID")
    base_currency: str = Field(default="CAD", alias="BASE_CURRENCY")
    default_timezone: str = Field(default=DEFAULT_TIMEZONE, alias="DEFAULT_TIMEZONE")
    logs_path: Path = Field(default=Path("logs"))
    spread_pips_default: PositiveFloat = Field(default=0.8)
    enable_prometheus: bool = Field(default=False, alias="ENABLE_PROMETHEUS")

    class Config:
        env_prefix = ""

    def validate_practice_only(self) -> None:
        if self.oanda_env != "practice":
            msg = "Only OANDA practice environment is supported."
            raise ValueError(msg)

    @property
    def timezone(self) -> pendulum.Timezone:
        return pendulum.timezone(self.default_timezone or DEFAULT_TIMEZONE)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_practice_only()
    return settings


__all__ = ["Settings", "get_settings", "DEFAULT_TIMEZONE"]
