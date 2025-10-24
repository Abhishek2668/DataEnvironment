"""Database models for trading data."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

metadata = MetaData()
Base = declarative_base(metadata=metadata)


class RunORM(Base):
    __tablename__ = "runs"

    id = Column(String, primary_key=True)
    instrument = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    mode = Column(String, nullable=False)
    status = Column(String, nullable=False, default="running")
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    stopped_at = Column(DateTime)

    orders = relationship("OrderORM", back_populates="run")
    positions = relationship("PositionORM", back_populates="run")


class CandleORM(Base):
    __tablename__ = "candles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instrument = Column(String, index=True, nullable=False)
    timeframe = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)


class OrderORM(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    run_id = Column(String, ForeignKey("runs.id"), nullable=False, index=True)
    instrument = Column(String, nullable=False)
    direction = Column(String, nullable=False)
    units = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    executed_at = Column(DateTime)

    run = relationship("RunORM", back_populates="orders")


class PositionORM(Base):
    __tablename__ = "positions"

    id = Column(String, primary_key=True)
    run_id = Column(String, ForeignKey("runs.id"), nullable=False, index=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    instrument = Column(String, nullable=False)
    direction = Column(String, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float)
    units = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="open")
    opened_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    closed_at = Column(DateTime)
    pnl = Column(Float)

    run = relationship("RunORM", back_populates="positions")


@dataclass(slots=True)
class Candle:
    instrument: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class Order(BaseModel):
    id: str
    run_id: str
    instrument: str
    direction: str
    units: int
    price: float
    status: str
    created_at: datetime
    executed_at: datetime | None = None


class Position(BaseModel):
    id: str
    run_id: str
    order_id: str
    instrument: str
    direction: str
    entry_price: float
    exit_price: float | None = None
    units: int
    status: str
    opened_at: datetime
    closed_at: datetime | None = None
    pnl: float | None = None


class Run(BaseModel):
    id: str
    instrument: str
    timeframe: str
    mode: str
    status: str
    started_at: datetime
    stopped_at: datetime | None = None


def create_session_factory(db_path: str) -> sessionmaker:
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


__all__ = [
    "Base",
    "metadata",
    "RunORM",
    "CandleORM",
    "OrderORM",
    "PositionORM",
    "Candle",
    "Order",
    "Position",
    "Run",
    "create_session_factory",
]
