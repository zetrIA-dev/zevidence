import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from zevidence.application import InMemoryRepository
from zevidence.domain import Run, RunEvent


class YieldingInMemoryRepository(InMemoryRepository):
    """Expose the scheduling point that real async persistence introduces."""

    async def _before_run_insert(self) -> None:
        await asyncio.sleep(0)


class FailOnceOutboxAckRepository(InMemoryRepository):
    def __init__(self) -> None:
        super().__init__()
        self._failed_once = False

    async def mark_outbox_published(
        self, record_id: UUID, *, published_at: datetime
    ) -> None:
        if not self._failed_once:
            self._failed_once = True
            raise RuntimeError("synthetic outbox acknowledgement failure")
        await super().mark_outbox_published(
            record_id,
            published_at=published_at,
        )


class CompleteAfterEventSnapshotRepository(InMemoryRepository):
    def __init__(self) -> None:
        super().__init__()
        self._completion: tuple[UUID, int, datetime] | None = None

    def complete_after_next_event_snapshot(
        self,
        *,
        run_id: UUID,
        attempt: int,
        occurred_at: datetime,
    ) -> None:
        self._completion = (run_id, attempt, occurred_at)

    async def list_run_events(
        self, run_id: UUID, *, after_sequence: int = 0
    ) -> tuple[RunEvent, ...]:
        events = await super().list_run_events(
            run_id,
            after_sequence=after_sequence,
        )
        completion = self._completion
        if completion is not None:
            self._completion = None
            completion_run_id, attempt, occurred_at = completion
            await self.complete_run(
                completion_run_id,
                attempt=attempt,
                occurred_at=occurred_at,
            )
        return events


@dataclass
class ScriptedProcessor:
    outcomes: list[Exception | None]
    processed_run_ids: list[UUID] = field(default_factory=list)

    async def process(self, run: Run) -> None:
        self.processed_run_ids.append(run.id)
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if outcome is not None:
            raise outcome
