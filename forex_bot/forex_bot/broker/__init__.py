"""Broker implementations."""
from __future__ import annotations

from forex_bot.broker.oanda import OandaBroker
from forex_bot.broker.paper import PaperBroker

def get_broker(name: str, settings=None, store=None, bus=None):
    """Return broker instance based on configuration name."""
    name = name.lower()
    if name == "oanda":
        return OandaBroker(settings, store, bus)
    elif name == "paper":
        return PaperBroker(settings, store, bus)
    else:
        raise ValueError(f"Unknown broker type: {name}")


__all__ = ["OandaBroker", "PaperBroker", "get_broker"]
