# coding: utf-8
"""Transactional repository for persistent strategy sessions."""

import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, select, update
from sqlalchemy.orm import Mapped, mapped_column

from trading_v2.agent.models import CompilationResult
from trading_v2.domain.enums import AssetClass, TradingMode
from trading_v2.sessions.models import (
    ChatMessage,
    PromptVersion,
    SessionSnapshot,
    SessionStatus,
    TradingSession,
)
from trading_v2.storage.database import Base, Database


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class SessionRecord(Base):
    __tablename__ = "trading_sessions_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    symbol: Mapped[str] = mapped_column(String(40))
    venue: Mapped[str] = mapped_column(String(20))
    asset_class: Mapped[str] = mapped_column(String(30))
    timeframe: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20))
    mode: Mapped[str] = mapped_column(String(20))
    pnl_percent: Mapped[float] = mapped_column(Float, default=0)
    prompt_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MessageRecord(Base):
    __tablename__ = "trading_messages_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("trading_sessions_v2.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="complete")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class PromptVersionRecord(Base):
    __tablename__ = "trading_prompt_versions_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("trading_sessions_v2.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    prompt_text: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(String(200))
    strategy_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    model_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SessionRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def initialize(self) -> None:
        self.database.create_schema()

    def list_sessions(self) -> list[TradingSession]:
        with self.database.sessions() as db:
            records = db.scalars(
                select(SessionRecord)
                .where(SessionRecord.status != SessionStatus.ARCHIVED.value)
                .order_by(SessionRecord.updated_at.desc())
            ).all()
            return [self._session(record) for record in records]

    def get_session(self, session_id: str) -> TradingSession | None:
        with self.database.sessions() as db:
            record = db.get(SessionRecord, session_id)
            return self._session(record) if record else None

    def get_snapshot(self, session_id: str) -> SessionSnapshot | None:
        with self.database.sessions() as db:
            session = db.get(SessionRecord, session_id)
            if session is None:
                return None
            messages = db.scalars(
                select(MessageRecord)
                .where(MessageRecord.session_id == session_id)
                .order_by(MessageRecord.created_at.asc())
            ).all()
            versions = db.scalars(
                select(PromptVersionRecord)
                .where(PromptVersionRecord.session_id == session_id)
                .order_by(PromptVersionRecord.version.desc())
            ).all()
            return SessionSnapshot(
                session=self._session(session),
                messages=[self._message(item) for item in messages],
                prompt_versions=[self._version(item) for item in versions],
            )

    def latest_strategy(self, session_id: str) -> dict | None:
        result = self.latest_strategy_with_version(session_id)
        return result[1] if result else None

    def latest_strategy_with_version(self, session_id: str) -> tuple[int, dict] | None:
        with self.database.sessions() as db:
            record = db.scalar(
                select(PromptVersionRecord)
                .where(
                    PromptVersionRecord.session_id == session_id,
                    PromptVersionRecord.strategy_json.is_not(None),
                )
                .order_by(PromptVersionRecord.version.desc())
            )
            if record is None or not record.strategy_json:
                return None
            return record.version, json.loads(record.strategy_json)

    def create_session(
        self,
        session: TradingSession,
        user_content: str,
        compilation: CompilationResult,
    ) -> SessionSnapshot:
        with self.database.sessions.begin() as db:
            record = SessionRecord(
                id=session.id,
                name=session.name,
                symbol=session.symbol,
                venue=session.venue,
                asset_class=session.asset_class.value,
                timeframe=session.timeframe,
                status=session.status.value,
                mode=session.mode.value,
                pnl_percent=session.pnl_percent,
                prompt_version=1,
                created_at=session.created_at,
                updated_at=session.updated_at,
            )
            db.add(record)
            self._add_turn(db, record, user_content, compilation, 1)
        snapshot = self.get_snapshot(session.id)
        if snapshot is None:
            raise RuntimeError("created session disappeared")
        return snapshot

    def append_turn(
        self,
        session_id: str,
        user_content: str,
        compilation: CompilationResult,
    ) -> ChatMessage | None:
        now = utc_now()
        with self.database.sessions.begin() as db:
            record = db.get(SessionRecord, session_id)
            if record is None:
                return None
            version = record.prompt_version + 1
            record.prompt_version = version
            record.updated_at = now
            if compilation.strategy is not None:
                asset_class, venue, symbol = compilation.strategy.instrument.split(":")
                record.name = compilation.strategy.name
                record.asset_class = AssetClass(asset_class).value
                record.venue = venue.upper()
                record.symbol = symbol.upper()
                record.timeframe = compilation.strategy.timeframe
            assistant = self._add_turn(db, record, user_content, compilation, version)
            assistant_id = assistant.id
        with self.database.sessions() as db:
            saved = db.get(MessageRecord, assistant_id)
            return self._message(saved) if saved else None

    def set_status(self, session_id: str, status: SessionStatus) -> TradingSession | None:
        with self.database.sessions.begin() as db:
            record = db.get(SessionRecord, session_id)
            if record is None:
                return None
            record.status = status.value
            record.updated_at = utc_now()
        return self.get_session(session_id)

    def _add_turn(self, db, record, user_content, compilation, version):
        now = utc_now()
        db.execute(
            update(PromptVersionRecord)
            .where(PromptVersionRecord.session_id == record.id)
            .values(active=False)
        )
        db.add(MessageRecord(
            id=str(uuid4()), session_id=record.id, role="user", content=user_content,
            version=version, status="complete", created_at=now,
        ))
        assistant = MessageRecord(
            id=str(uuid4()), session_id=record.id, role="assistant",
            content=compilation.assistant_content, version=version,
            status="complete", created_at=now,
        )
        db.add(assistant)
        db.add(PromptVersionRecord(
            id=str(uuid4()), session_id=record.id, version=version,
            prompt_text=user_content, summary=compilation.summary,
            strategy_json=(
                compilation.strategy.model_dump_json() if compilation.strategy is not None else None
            ),
            active=True, model_provider=compilation.model_provider,
            model_name=compilation.model_name, warning=compilation.warning, created_at=now,
        ))
        return assistant

    @staticmethod
    def _session(record: SessionRecord) -> TradingSession:
        return TradingSession(
            id=record.id, name=record.name, symbol=record.symbol, venue=record.venue,
            asset_class=AssetClass(record.asset_class), timeframe=record.timeframe,
            status=SessionStatus(record.status), mode=TradingMode(record.mode),
            pnl_percent=record.pnl_percent, prompt_version=record.prompt_version,
            created_at=aware(record.created_at), updated_at=aware(record.updated_at),
        )

    @staticmethod
    def _message(record: MessageRecord) -> ChatMessage:
        return ChatMessage(
            id=record.id, session_id=record.session_id, role=record.role,
            content=record.content, version=record.version, status=record.status,
            created_at=aware(record.created_at),
        )

    @staticmethod
    def _version(record: PromptVersionRecord) -> PromptVersion:
        return PromptVersion(
            id=record.id, session_id=record.session_id, version=record.version,
            prompt_text=record.prompt_text, summary=record.summary,
            strategy=json.loads(record.strategy_json) if record.strategy_json else None,
            active=record.active, model_provider=record.model_provider,
            model_name=record.model_name, warning=record.warning,
            created_at=aware(record.created_at),
        )
