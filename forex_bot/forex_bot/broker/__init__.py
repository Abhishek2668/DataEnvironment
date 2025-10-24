"""Broker implementations."""
from __future__ import annotations

from forex_bot.broker.oanda import OandaBroker
from forex_bot.broker.paper import PaperBroker

__all__ = ["OandaBroker", "PaperBroker"]
