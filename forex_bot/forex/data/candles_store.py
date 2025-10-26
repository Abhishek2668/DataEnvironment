from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from sqlalchemy import Select, create_engine, select
from sqlalchemy.orm import Session

from forex.data.models import Base, Candle


class CandleStore:
    def __init__(self, database_path: Path | str = "sqlite:///forex.db") -> None:
        self.engine = create_engine(f"sqlite:///{database_path}", future=True)
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        with Session(self.engine) as session:
            yield session

    def upsert_candles(self, candles: Iterable[Candle]) -> None:
        with self.session() as session:
            for candle in candles:
                existing = (
                    session.execute(
                        select(Candle)
                        .where(Candle.instrument == candle.instrument)
                        .where(Candle.time == candle.time)
                        .where(Candle.granularity == candle.granularity)
                    )
                    .scalars()
                    .first()
                )
                if existing:
                    for field in ("open", "high", "low", "close", "volume"):
                        setattr(existing, field, getattr(candle, field))
                else:
                    session.add(candle)
            session.commit()

    def load_candles(
        self,
        instrument: str,
        granularity: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Sequence[Candle]:
        query: Select[tuple[Candle]] = select(Candle).where(Candle.instrument == instrument).where(
            Candle.granularity == granularity
        )
        if start:
            query = query.where(Candle.time >= start)
        if end:
            query = query.where(Candle.time <= end)
        query = query.order_by(Candle.time)
        with self.session() as session:
            return session.execute(query).scalars().all()


__all__ = ["CandleStore"]
