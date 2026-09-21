# coding: utf-8
"""Small in-process event stream used by the V2 control plane.

The stream is intentionally not a message broker.  It provides a bounded event
history and bounded per-client queues for UI updates.  Durable audit events will
later be written by a repository subscriber without changing publishers.
"""

import asyncio
from collections import deque
from datetime import datetime
from typing import Any, AsyncIterator
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from trading_v2.domain.base import require_aware_datetime, utc_now


class EventEnvelope(BaseModel):
    """Provider-neutral event sent between V2 services and the UI."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    sequence: int = Field(ge=1)
    topic: str
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=utc_now)

    @field_validator("topic")
    @classmethod
    def topic_required(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("event topic cannot be empty")
        return normalized

    @field_validator("occurred_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        return require_aware_datetime(value, "occurred_at")


class EventSubscription(AsyncIterator[EventEnvelope]):
    """A bounded asynchronous event subscription."""

    _END = object()

    def __init__(
        self,
        stream: "InMemoryEventStream",
        queue: asyncio.Queue[Any],
    ) -> None:
        self._stream = stream
        self._queue = queue
        self._closed = False
        self.dropped_events = 0

    def __aiter__(self) -> "EventSubscription":
        return self

    async def __anext__(self) -> EventEnvelope:
        item = await self._queue.get()
        if item is self._END:
            raise StopAsyncIteration
        return item

    async def get(self) -> EventEnvelope:
        """Wait for one event; raises when the subscription is closed."""

        try:
            return await self.__anext__()
        except StopAsyncIteration as exc:
            raise RuntimeError("event subscription is closed") from exc

    async def close(self) -> None:
        if self._closed:
            return
        await self._stream.unsubscribe(self)

    def _offer(self, item: EventEnvelope) -> None:
        if self._closed:
            return
        if self._queue.full():
            try:
                self._queue.get_nowait()
                self.dropped_events += 1
            except asyncio.QueueEmpty:
                pass
        self._queue.put_nowait(item)

    def _mark_closed(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self._queue.put_nowait(self._END)


class InMemoryEventStream:
    """Fan-out stream with bounded history and slow-consumer protection."""

    def __init__(self, history_size: int = 2_000, subscriber_queue_size: int = 500) -> None:
        if history_size <= 0 or subscriber_queue_size <= 0:
            raise ValueError("event stream sizes must be positive")
        self._history: deque[EventEnvelope] = deque(maxlen=history_size)
        self._subscriber_queue_size = subscriber_queue_size
        self._subscriptions: set[EventSubscription] = set()
        self._next_sequence = 1
        self._closed = False
        self._lock = asyncio.Lock()

    @property
    def closed(self) -> bool:
        return self._closed

    async def publish(self, topic: str, payload: dict[str, Any] | None = None) -> EventEnvelope:
        async with self._lock:
            if self._closed:
                raise RuntimeError("event stream is closed")
            event = EventEnvelope(
                sequence=self._next_sequence,
                topic=topic,
                payload=payload or {},
            )
            self._next_sequence += 1
            self._history.append(event)
            subscriptions = tuple(self._subscriptions)

        for subscription in subscriptions:
            subscription._offer(event)
        return event

    async def subscribe(
        self,
        replay: int = 0,
        queue_size: int | None = None,
    ) -> EventSubscription:
        if replay < 0:
            raise ValueError("replay cannot be negative")
        actual_queue_size = queue_size or self._subscriber_queue_size
        if actual_queue_size <= 0:
            raise ValueError("queue_size must be positive")

        queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=actual_queue_size)
        subscription = EventSubscription(self, queue)
        async with self._lock:
            if self._closed:
                raise RuntimeError("event stream is closed")
            history = list(self._history)[-min(replay, actual_queue_size):] if replay else []
            self._subscriptions.add(subscription)

        for event in history:
            subscription._offer(event)
        return subscription

    async def unsubscribe(self, subscription: EventSubscription) -> None:
        async with self._lock:
            self._subscriptions.discard(subscription)
        subscription._mark_closed()

    async def recent(self, limit: int = 100) -> list[EventEnvelope]:
        if limit < 0:
            raise ValueError("limit cannot be negative")
        async with self._lock:
            if limit == 0:
                return []
            return list(self._history)[-limit:]

    async def close(self) -> None:
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            subscriptions = tuple(self._subscriptions)
            self._subscriptions.clear()
        for subscription in subscriptions:
            subscription._mark_closed()
