# coding: utf-8
"""Persistence and UI projections for deterministic candidate signals."""

import json
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from trading_v2.domain.signal import Signal
from trading_v2.storage.database import Base, Database


class SignalRecord(Base):
    __tablename__ = "candidate_signals_v2"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "strategy_version", "instrument", "timeframe",
            "bar_time", "side", name="uq_candidate_signal_bar",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("trading_sessions_v2.id", ondelete="CASCADE"), index=True
    )
    strategy_version: Mapped[int] = mapped_column(Integer)
    instrument: Mapped[str] = mapped_column(String(100))
    timeframe: Mapped[str] = mapped_column(String(10))
    side: Mapped[str] = mapped_column(String(20))
    strength: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(String(300))
    bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    indicators_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SignalRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def save(self, signal: Signal) -> bool:
        try:
            with self.database.sessions.begin() as db:
                db.add(SignalRecord(
                    id=str(signal.id), session_id=str(signal.session_id),
                    strategy_version=signal.strategy_version,
                    instrument=signal.instrument.canonical, timeframe=signal.timeframe,
                    side=signal.side.value, strength=signal.strength,
                    reason=signal.reason, bar_time=signal.bar_time,
                    indicators_json=json.dumps(signal.indicators, ensure_ascii=False),
                    created_at=signal.created_at, expires_at=signal.expires_at,
                ))
            return True
        except IntegrityError:
            return False

    def list_for_session(self, session_id: str, limit: int = 200) -> list[dict]:
        with self.database.sessions() as db:
            records = db.scalars(
                select(SignalRecord)
                .where(SignalRecord.session_id == session_id)
                .order_by(SignalRecord.bar_time.desc())
                .limit(limit)
            ).all()
        return [self._projection(record) for record in reversed(records)]

    @staticmethod
    def _projection(record: SignalRecord) -> dict:
        indicators = json.loads(record.indicators_json)
        side = "BUY" if record.side == "buy" else "SELL"
        bar_time = record.bar_time
        if bar_time.tzinfo is None:
            bar_time = bar_time.replace(tzinfo=timezone.utc)
        return {
            "id": record.id,
            "timestamp": bar_time.isoformat(),
            "price": indicators.get("close"),
            "side": side,
            "state": "candidate",
            "label": record.reason,
            "confidence": record.strength,
            "strategy_version": record.strategy_version,
            "indicators": indicators,
        }

    @staticmethod
    def event_projection(signal: dict) -> dict:
        return {
            "id": signal["id"], "timestamp": signal["timestamp"], "type": "signal",
            "title": signal["label"],
            "detail": f"{signal['side']} · {signal['price']} · 策略 v{signal['strategy_version']}",
            "state": "success",
        }
