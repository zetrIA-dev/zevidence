"""Repository contract and deterministic in-memory adapter."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import UUID

import anyio

from zevidence.application.errors import IdempotencyConflict
from zevidence.domain import (
    Document,
    Dossier,
    JobMessage,
    OutboxRecord,
    Run,
    RunError,
    RunEvent,
    RunEventType,
    RunLease,
    RunStatus,
    transition_run,
)


class ClaimDisposition(StrEnum):
    ACQUIRED = "acquired"
    TERMINAL = "terminal"
    LEASE_HELD = "lease_held"
    RETRY_NOT_DUE = "retry_not_due"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class RunClaimResult:
    disposition: ClaimDisposition
    lease: RunLease | None = None
    retry_at: datetime | None = None


class Repository(Protocol):
    async def add_dossier(self, dossier: Dossier) -> None: ...

    async def get_dossier(self, dossier_id: UUID) -> Dossier | None: ...

    async def add_document(self, document: Document, content: str) -> None: ...

    async def get_document(self, document_id: UUID) -> Document | None: ...

    async def get_document_content(self, document_id: UUID) -> str | None: ...

    async def get_run(self, run_id: UUID) -> Run | None: ...

    async def create_run_once(self, run: Run) -> tuple[Run, bool]: ...

    async def list_pending_outbox(self) -> tuple[OutboxRecord, ...]: ...

    async def mark_outbox_published(
        self, record_id: UUID, *, published_at: datetime
    ) -> None: ...

    async def claim_run(
        self,
        run_id: UUID,
        *,
        worker_id: str,
        now: datetime,
        lease_duration: timedelta,
    ) -> RunClaimResult: ...

    async def schedule_retry(
        self,
        run_id: UUID,
        *,
        attempt: int,
        error_code: str,
        occurred_at: datetime,
        retry_at: datetime,
    ) -> bool: ...

    async def complete_run(
        self, run_id: UUID, *, attempt: int, occurred_at: datetime
    ) -> bool: ...

    async def fail_run(
        self,
        run_id: UUID,
        *,
        attempt: int,
        error: RunError,
        occurred_at: datetime,
        dead_lettered: bool = False,
    ) -> bool: ...

    async def list_run_events(
        self, run_id: UUID, *, after_sequence: int = 0
    ) -> tuple[RunEvent, ...]: ...

    async def wait_for_run_events(
        self, run_id: UUID, *, after_sequence: int
    ) -> None: ...


class InMemoryRepository:
    """In-memory adapter with atomic idempotent run creation."""

    def __init__(self) -> None:
        self._dossiers: dict[UUID, Dossier] = {}
        self._documents: dict[UUID, Document] = {}
        self._document_contents: dict[UUID, str] = {}
        self._runs: dict[UUID, Run] = {}
        self._run_keys: dict[tuple[UUID, str], UUID] = {}
        self._outbox: dict[UUID, OutboxRecord] = {}
        self._run_leases: dict[UUID, RunLease] = {}
        self._retry_not_before: dict[UUID, datetime] = {}
        self._run_events: dict[UUID, list[RunEvent]] = {}
        self._run_event_signals: dict[UUID, anyio.Event] = {}
        self._run_lock = anyio.Lock()

    async def add_dossier(self, dossier: Dossier) -> None:
        self._dossiers[dossier.id] = dossier

    async def get_dossier(self, dossier_id: UUID) -> Dossier | None:
        return self._dossiers.get(dossier_id)

    async def add_document(self, document: Document, content: str) -> None:
        self._documents[document.id] = document
        self._document_contents[document.id] = content

    async def get_document(self, document_id: UUID) -> Document | None:
        return self._documents.get(document_id)

    async def get_document_content(self, document_id: UUID) -> str | None:
        return self._document_contents.get(document_id)

    async def get_run(self, run_id: UUID) -> Run | None:
        return self._runs.get(run_id)

    async def _before_run_insert(self) -> None:
        """Allow tests to expose a check-then-insert scheduling boundary."""

    async def create_run_once(self, run: Run) -> tuple[Run, bool]:
        key = (run.dossier_id, run.idempotency_key)
        async with self._run_lock:
            existing_id = self._run_keys.get(key)
            if existing_id is not None:
                existing = self._runs[existing_id]
                if existing.document_ids != run.document_ids:
                    raise IdempotencyConflict(
                        "idempotency key was already used with a different request"
                    )
                return existing, True

            message = JobMessage(run_id=run.id)
            outbox_record = OutboxRecord(message=message)
            queued_event = RunEvent(
                run_id=run.id,
                sequence=1,
                event_type=RunEventType.QUEUED,
                occurred_at=message.enqueued_at,
            )
            await self._before_run_insert()
            self._runs[run.id] = run
            self._run_keys[key] = run.id
            self._outbox[outbox_record.id] = outbox_record
            self._run_events[run.id] = [queued_event]
            self._run_event_signals[run.id] = anyio.Event()
            return run, False

    async def list_pending_outbox(self) -> tuple[OutboxRecord, ...]:
        async with self._run_lock:
            return tuple(
                record
                for record in self._outbox.values()
                if record.published_at is None
            )

    async def mark_outbox_published(
        self, record_id: UUID, *, published_at: datetime
    ) -> None:
        async with self._run_lock:
            record = self._outbox[record_id]
            self._outbox[record_id] = record.model_copy(
                update={"published_at": published_at}
            )

    def _append_run_event(
        self,
        run_id: UUID,
        *,
        event_type: RunEventType,
        occurred_at: datetime,
        attempt: int | None = None,
        error_code: str | None = None,
    ) -> RunEvent:
        events = self._run_events.setdefault(run_id, [])
        event = RunEvent(
            run_id=run_id,
            sequence=len(events) + 1,
            event_type=event_type,
            occurred_at=occurred_at,
            attempt=attempt,
            error_code=error_code,
        )
        events.append(event)
        signal = self._run_event_signals.get(run_id)
        if signal is not None:
            signal.set()
        self._run_event_signals[run_id] = anyio.Event()
        return event

    async def claim_run(
        self,
        run_id: UUID,
        *,
        worker_id: str,
        now: datetime,
        lease_duration: timedelta,
    ) -> RunClaimResult:
        async with self._run_lock:
            run = self._runs.get(run_id)
            if run is None:
                return RunClaimResult(ClaimDisposition.MISSING)
            if run.status in {RunStatus.COMPLETED, RunStatus.FAILED}:
                return RunClaimResult(ClaimDisposition.TERMINAL)

            current_lease = self._run_leases.get(run_id)
            if (
                run.status is RunStatus.RUNNING
                and current_lease is not None
                and current_lease.expires_at > now
            ):
                return RunClaimResult(
                    ClaimDisposition.LEASE_HELD,
                    retry_at=current_lease.expires_at,
                )
            retry_not_before = self._retry_not_before.get(run_id)
            if (
                run.status is RunStatus.RETRY_SCHEDULED
                and retry_not_before is not None
                and retry_not_before > now
            ):
                return RunClaimResult(
                    ClaimDisposition.RETRY_NOT_DUE,
                    retry_at=retry_not_before,
                )

            attempt = 1 if current_lease is None else current_lease.attempt + 1
            reclaimed = run.status is RunStatus.RUNNING
            if not reclaimed:
                run = transition_run(run, RunStatus.RUNNING, occurred_at=now)
                self._runs[run_id] = run

            lease = RunLease(
                run_id=run_id,
                worker_id=worker_id,
                attempt=attempt,
                expires_at=now + lease_duration,
            )
            self._run_leases[run_id] = lease
            self._retry_not_before.pop(run_id, None)
            self._append_run_event(
                run_id,
                event_type=(
                    RunEventType.RECLAIMED if reclaimed else RunEventType.STARTED
                ),
                occurred_at=now,
                attempt=attempt,
            )
            return RunClaimResult(
                ClaimDisposition.ACQUIRED,
                lease=lease,
            )

    def _owns_attempt(self, run_id: UUID, attempt: int) -> bool:
        lease = self._run_leases.get(run_id)
        return lease is not None and lease.attempt == attempt

    async def schedule_retry(
        self,
        run_id: UUID,
        *,
        attempt: int,
        error_code: str,
        occurred_at: datetime,
        retry_at: datetime,
    ) -> bool:
        async with self._run_lock:
            if not self._owns_attempt(run_id, attempt):
                return False
            run = self._runs[run_id]
            if run.status is not RunStatus.RUNNING:
                return False
            self._runs[run_id] = transition_run(
                run,
                RunStatus.RETRY_SCHEDULED,
                occurred_at=occurred_at,
            )
            self._retry_not_before[run_id] = retry_at
            self._append_run_event(
                run_id,
                event_type=RunEventType.RETRY_SCHEDULED,
                occurred_at=occurred_at,
                attempt=attempt,
                error_code=error_code,
            )
            return True

    async def complete_run(
        self, run_id: UUID, *, attempt: int, occurred_at: datetime
    ) -> bool:
        async with self._run_lock:
            if not self._owns_attempt(run_id, attempt):
                return False
            run = self._runs[run_id]
            if run.status is not RunStatus.RUNNING:
                return False
            self._runs[run_id] = transition_run(
                run,
                RunStatus.COMPLETED,
                occurred_at=occurred_at,
            )
            self._append_run_event(
                run_id,
                event_type=RunEventType.COMPLETED,
                occurred_at=occurred_at,
                attempt=attempt,
            )
            return True

    async def fail_run(
        self,
        run_id: UUID,
        *,
        attempt: int,
        error: RunError,
        occurred_at: datetime,
        dead_lettered: bool = False,
    ) -> bool:
        async with self._run_lock:
            if not self._owns_attempt(run_id, attempt):
                return False
            run = self._runs[run_id]
            if run.status not in {RunStatus.RUNNING, RunStatus.RETRY_SCHEDULED}:
                return False
            self._runs[run_id] = transition_run(
                run,
                RunStatus.FAILED,
                error=error,
                occurred_at=occurred_at,
            )
            self._append_run_event(
                run_id,
                event_type=RunEventType.FAILED,
                occurred_at=occurred_at,
                attempt=attempt,
                error_code=error.code,
            )
            if dead_lettered:
                self._append_run_event(
                    run_id,
                    event_type=RunEventType.DEAD_LETTERED,
                    occurred_at=occurred_at,
                    attempt=attempt,
                    error_code=error.code,
                )
            return True

    async def list_run_events(
        self, run_id: UUID, *, after_sequence: int = 0
    ) -> tuple[RunEvent, ...]:
        async with self._run_lock:
            return tuple(
                event
                for event in self._run_events.get(run_id, [])
                if event.sequence > after_sequence
            )

    async def wait_for_run_events(self, run_id: UUID, *, after_sequence: int) -> None:
        async with self._run_lock:
            if any(
                event.sequence > after_sequence
                for event in self._run_events.get(run_id, [])
            ):
                return
            signal = self._run_event_signals.setdefault(run_id, anyio.Event())
        await signal.wait()
