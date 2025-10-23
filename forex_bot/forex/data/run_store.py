from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, Sequence

from sqlalchemy import Select, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from forex.data.models import Base, RunMetricRecord, RunRecord
from forex.utils.time import utc_now


@dataclass(slots=True)
class RunSummary:
    id: str
    type: str
    status: str
    strategy: str
    instrument: str
    granularity: str
    started_at: datetime
    ended_at: datetime | None
    config: dict


class RunStore:
    def __init__(self, engine: Engine | None = None, database_path: str | None = None) -> None:
        if engine is None:
            db_path = database_path or "sqlite:///forex.db"
            engine = create_engine(db_path, future=True)
        self.engine = engine
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        with Session(self.engine) as session:
            yield session

    def start_run(
        self,
        run_id: str,
        *,
        run_type: str,
        strategy: str,
        instrument: str,
        granularity: str,
        config: dict,
    ) -> None:
        record = RunRecord(
            id=run_id,
            type=run_type,
            status="running",
            strategy=strategy,
            instrument=instrument,
            granularity=granularity,
            started_at=utc_now(),
            config=json.dumps(config, default=str),
        )
        with self.session() as session:
            session.merge(record)
            session.commit()

    def finish_run(self, run_id: str, status: str = "completed") -> None:
        with self.session() as session:
            record = session.get(RunRecord, run_id)
            if not record:
                return
            record.status = status
            record.ended_at = utc_now()
            session.add(record)
            session.commit()

    def save_metrics(self, run_id: str, metrics: dict, equity_curve: Sequence[dict]) -> None:
        payload = RunMetricRecord(
            run_id=run_id,
            metrics=json.dumps(metrics, default=str),
            equity_curve=json.dumps(list(equity_curve), default=str),
        )
        with self.session() as session:
            session.add(payload)
            session.commit()

    def get_metrics(self, run_id: str) -> dict | None:
        with self.session() as session:
            stmt: Select[tuple[RunMetricRecord]] = (
                select(RunMetricRecord)
                .where(RunMetricRecord.run_id == run_id)
                .order_by(RunMetricRecord.id.desc())
                .limit(1)
            )
            record = session.execute(stmt).scalars().first()
            if not record:
                return None
            return {
                "metrics": json.loads(record.metrics),
                "equity_curve": json.loads(record.equity_curve),
            }

    def list_runs(self, limit: int = 25) -> list[RunSummary]:
        with self.session() as session:
            stmt: Select[tuple[RunRecord]] = (
                select(RunRecord)
                .order_by(RunRecord.started_at.desc())
                .limit(limit)
            )
            records = session.execute(stmt).scalars().all()
            summaries: list[RunSummary] = []
            for record in records:
                config = json.loads(record.config) if record.config else {}
                summaries.append(
                    RunSummary(
                        id=record.id,
                        type=record.type,
                        status=record.status,
                        strategy=record.strategy,
                        instrument=record.instrument,
                        granularity=record.granularity,
                        started_at=record.started_at,
                        ended_at=record.ended_at,
                        config=config,
                    )
                )
            return summaries


__all__ = ["RunStore", "RunSummary"]

