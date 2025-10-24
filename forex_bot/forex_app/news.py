"""News ingestion from free providers with caching."""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Any

import httpx

from .models import NewsItem
from .settings import Settings

SYMBOLS = ["USD", "CAD", "EUR", "GBP", "JPY", "AUD", "CHF", "NZD"]


def _estimate_sentiment(text: str) -> float:
    positive_words = {"gain", "rise", "bullish", "optimistic", "beat"}
    negative_words = {"fall", "drop", "bearish", "pessimistic", "miss"}
    text_lower = text.lower()
    score = sum(1 for word in positive_words if word in text_lower) - sum(
        1 for word in negative_words if word in text_lower
    )
    return max(-1.0, min(1.0, score / 5))


def _tag_symbols(text: str) -> list[str]:
    tokens = text.upper().split()
    tags = set()
    for base in SYMBOLS:
        for quote in SYMBOLS:
            if base == quote:
                continue
            pair = f"{base}/{quote}"
            if base in tokens and quote in tokens:
                tags.add(pair)
    return sorted(tags)


class NewsService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: httpx.AsyncClient | None = None
        self._cache: list[NewsItem] = []
        self._cache_expiry: datetime | None = None
        self._lock = asyncio.Lock()

    async def _client_instance(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fetch_news(self) -> list[NewsItem]:
        async with self._lock:
            now = datetime.utcnow()
            if self._cache_expiry and now < self._cache_expiry:
                return self._cache
            if self.settings.NEWS_PROVIDER == "gdelt":
                items = await self._fetch_gdelt()
            else:
                items = await self._fetch_gdelt()  # fallback to GDELT
            self._cache = items
            self._cache_expiry = now + timedelta(minutes=5)
            return items

    async def _fetch_gdelt(self) -> list[NewsItem]:
        client = await self._client_instance()
        params = {"query": " OR ".join(SYMBOLS), "format": "JSON", "maxrecords": 30, "timespan": "15MINUTES"}
        response = await client.get(str(self.settings.GDELT_BASE), params=params)
        response.raise_for_status()
        payload = response.json()
        seen: set[str] = set()
        items: list[NewsItem] = []
        for article in payload.get("articles", []):
            title = article.get("title", "")
            if not title:
                continue
            url = article.get("url", "")
            key = hashlib.sha256(url.encode("utf-8")).hexdigest()
            if key in seen:
                continue
            seen.add(key)
            try:
                ts = datetime.strptime(article.get("seendate"), "%Y%m%d%H%M%S")
            except (TypeError, ValueError):
                ts = datetime.utcnow()
            symbols = _tag_symbols(title)
            sentiment = _estimate_sentiment(title)
            impact = "high" if abs(sentiment) > 0.6 else ("medium" if abs(sentiment) > 0.3 else "low")
            items.append(
                NewsItem(
                    ts=ts,
                    title=title,
                    url=url,
                    source=article.get("source", "GDELT"),
                    sentiment=sentiment,
                    impact=impact,
                    symbols=symbols,
                )
            )
        return sorted(items, key=lambda item: item.ts, reverse=True)


__all__ = ["NewsService"]
