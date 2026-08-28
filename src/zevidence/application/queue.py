"""Deterministic at-least-once queue and transactional outbox publisher."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

import anyio

from zevidence.application.repository import Repository
from zevidence.domain import JobMessage


@dataclass(frozen=True, slots=True)
class QueueDelivery:
    receipt_id: UUID
    message: JobMessage
    delivery_count: int
    available_at: datetime


@dataclass(frozen=True, slots=True)
class DeadLetter:
    delivery: QueueDelivery
    reason: str
    failed_at: datetime


class Queue(Protocol):
    async def send(self, message: JobMessage) -> None: ...

    async def receive(self, *, now: datetime) -> QueueDelivery | None: ...

    async def ack(self, delivery: QueueDelivery) -> None: ...

    async def retry(
        self, delivery: QueueDelivery, *, available_at: datetime
    ) -> None: ...

    async def dead_letter(
        self, delivery: QueueDelivery, *, reason: str, failed_at: datetime
    ) -> None: ...


class InMemoryQueue:
    """Small queue adapter with explicit retry and dead-letter behavior."""

    def __init__(
        self,
        *,
        visibility_timeout: timedelta = timedelta(seconds=30),
    ) -> None:
        if visibility_timeout <= timedelta(0):
            raise ValueError("visibility_timeout must be positive")
        self._pending: list[QueueDelivery] = []
        self._in_flight: dict[UUID, tuple[QueueDelivery, datetime]] = {}
        self._dead_letters: list[DeadLetter] = []
        self._lock = anyio.Lock()
        self._visibility_timeout = visibility_timeout

    async def send(self, message: JobMessage) -> None:
        async with self._lock:
            self._pending.append(
                QueueDelivery(
                    receipt_id=uuid4(),
                    message=message,
                    delivery_count=0,
                    available_at=message.enqueued_at,
                )
            )

    async def receive(self, *, now: datetime) -> QueueDelivery | None:
        async with self._lock:
            expired_receipts = [
                receipt_id
                for receipt_id, (_, deadline) in self._in_flight.items()
                if deadline <= now
            ]
            for receipt_id in expired_receipts:
                expired, _ = self._in_flight.pop(receipt_id)
                self._pending.append(
                    QueueDelivery(
                        receipt_id=uuid4(),
                        message=expired.message,
                        delivery_count=expired.delivery_count,
                        available_at=now,
                    )
                )

            for index, delivery in enumerate(self._pending):
                if delivery.available_at <= now:
                    self._pending.pop(index)
                    received = QueueDelivery(
                        receipt_id=delivery.receipt_id,
                        message=delivery.message,
                        delivery_count=delivery.delivery_count + 1,
                        available_at=delivery.available_at,
                    )
                    self._in_flight[received.receipt_id] = (
                        received,
                        now + self._visibility_timeout,
                    )
                    return received
            return None

    async def ack(self, delivery: QueueDelivery) -> None:
        async with self._lock:
            self._in_flight.pop(delivery.receipt_id, None)

    async def retry(self, delivery: QueueDelivery, *, available_at: datetime) -> None:
        async with self._lock:
            self._in_flight.pop(delivery.receipt_id, None)
            self._pending.append(
                QueueDelivery(
                    receipt_id=uuid4(),
                    message=delivery.message,
                    delivery_count=delivery.delivery_count,
                    available_at=available_at,
                )
            )

    async def dead_letter(
        self, delivery: QueueDelivery, *, reason: str, failed_at: datetime
    ) -> None:
        async with self._lock:
            self._in_flight.pop(delivery.receipt_id, None)
            self._dead_letters.append(
                DeadLetter(delivery=delivery, reason=reason, failed_at=failed_at)
            )

    async def pending(self) -> tuple[QueueDelivery, ...]:
        async with self._lock:
            return tuple(self._pending)

    async def in_flight(self) -> tuple[QueueDelivery, ...]:
        async with self._lock:
            return tuple(delivery for delivery, _ in self._in_flight.values())

    async def dead_letters(self) -> tuple[DeadLetter, ...]:
        async with self._lock:
            return tuple(self._dead_letters)


class OutboxPublisher:
    """Publish durable outbox records and acknowledge them afterward."""

    def __init__(self, repository: Repository, queue: Queue) -> None:
        self._repository = repository
        self._queue = queue

    async def publish_pending(self, *, published_at: datetime) -> int:
        published = 0
        for record in await self._repository.list_pending_outbox():
            await self._queue.send(record.message)
            await self._repository.mark_outbox_published(
                record.id,
                published_at=published_at,
            )
            published += 1
        return published
