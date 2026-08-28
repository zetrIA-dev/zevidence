"""Idempotent run worker with leases, fencing, retries, and DLQ handling."""

import logging
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from zevidence.application.queue import Queue, QueueDelivery
from zevidence.application.repository import ClaimDisposition, Repository
from zevidence.domain import Run, RunError

logger = logging.getLogger(__name__)


class RetryableProcessingError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PermanentProcessingError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class RunProcessor(Protocol):
    async def process(self, run: Run) -> None: ...


class WorkerOutcome(StrEnum):
    IDLE = "idle"
    COMPLETED = "completed"
    RETRY_SCHEDULED = "retry_scheduled"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"
    DUPLICATE_IGNORED = "duplicate_ignored"
    DEFERRED = "deferred"
    STALE_ATTEMPT = "stale_attempt"


class RunWorker:
    def __init__(
        self,
        *,
        worker_id: str,
        repository: Repository,
        queue: Queue,
        processor: RunProcessor,
        lease_duration: timedelta = timedelta(seconds=30),
        retry_base_delay: timedelta = timedelta(seconds=5),
        max_attempts: int = 3,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        if lease_duration <= timedelta(0):
            raise ValueError("lease_duration must be positive")
        if retry_base_delay < timedelta(0):
            raise ValueError("retry_base_delay cannot be negative")
        self._worker_id = worker_id
        self._repository = repository
        self._queue = queue
        self._processor = processor
        self._lease_duration = lease_duration
        self._retry_base_delay = retry_base_delay
        self._max_attempts = max_attempts

    async def process_one(self, *, now: datetime) -> WorkerOutcome:
        delivery = await self._queue.receive(now=now)
        if delivery is None:
            return WorkerOutcome.IDLE

        run = await self._repository.get_run(delivery.message.run_id)
        if run is None:
            await self._queue.dead_letter(
                delivery,
                reason="run_not_found",
                failed_at=now,
            )
            return WorkerOutcome.DEAD_LETTERED

        claim = await self._repository.claim_run(
            run.id,
            worker_id=self._worker_id,
            now=now,
            lease_duration=self._lease_duration,
        )
        if claim.disposition is ClaimDisposition.TERMINAL:
            await self._queue.ack(delivery)
            return WorkerOutcome.DUPLICATE_IGNORED
        if claim.disposition in {
            ClaimDisposition.LEASE_HELD,
            ClaimDisposition.RETRY_NOT_DUE,
        }:
            if claim.retry_at is None:
                raise RuntimeError("deferred claim requires retry_at")
            await self._queue.retry(delivery, available_at=claim.retry_at)
            return WorkerOutcome.DEFERRED
        if claim.disposition is ClaimDisposition.MISSING:
            await self._queue.dead_letter(
                delivery,
                reason="run_disappeared",
                failed_at=now,
            )
            return WorkerOutcome.DEAD_LETTERED
        lease = claim.lease
        if lease is None:
            raise RuntimeError("acquired claim requires a lease")

        if lease.attempt > self._max_attempts:
            error = RunError(
                code="attempts_exhausted",
                message="run exceeded the worker attempt limit",
            )
            changed = await self._repository.fail_run(
                run.id,
                attempt=lease.attempt,
                error=error,
                occurred_at=now,
                dead_lettered=True,
            )
            if not changed:
                await self._queue.ack(delivery)
                return WorkerOutcome.STALE_ATTEMPT
            await self._queue.dead_letter(
                delivery,
                reason=error.code,
                failed_at=now,
            )
            return WorkerOutcome.DEAD_LETTERED

        run = await self._repository.get_run(run.id)
        if run is None:
            await self._queue.dead_letter(
                delivery,
                reason="run_disappeared",
                failed_at=now,
            )
            return WorkerOutcome.DEAD_LETTERED

        try:
            await self._processor.process(run)
        except PermanentProcessingError as error:
            changed = await self._repository.fail_run(
                run.id,
                attempt=lease.attempt,
                error=RunError(code=error.code, message=str(error)),
                occurred_at=now,
            )
            await self._queue.ack(delivery)
            return WorkerOutcome.FAILED if changed else WorkerOutcome.STALE_ATTEMPT
        except RetryableProcessingError as error:
            return await self._handle_retryable_failure(
                delivery,
                run=run,
                attempt=lease.attempt,
                code=error.code,
                message=str(error),
                now=now,
            )
        except Exception:
            logger.exception(
                "unexpected run processor failure",
                extra={"run_id": str(run.id), "attempt": lease.attempt},
            )
            return await self._handle_retryable_failure(
                delivery,
                run=run,
                attempt=lease.attempt,
                code="unexpected_processing_error",
                message="unexpected processing failure",
                now=now,
            )

        changed = await self._repository.complete_run(
            run.id,
            attempt=lease.attempt,
            occurred_at=now,
        )
        await self._queue.ack(delivery)
        return WorkerOutcome.COMPLETED if changed else WorkerOutcome.STALE_ATTEMPT

    async def _handle_retryable_failure(
        self,
        delivery: QueueDelivery,
        *,
        run: Run,
        attempt: int,
        code: str,
        message: str,
        now: datetime,
    ) -> WorkerOutcome:
        if attempt >= self._max_attempts:
            changed = await self._repository.fail_run(
                run.id,
                attempt=attempt,
                error=RunError(code=code, message=message),
                occurred_at=now,
                dead_lettered=True,
            )
            if not changed:
                await self._queue.ack(delivery)
                return WorkerOutcome.STALE_ATTEMPT
            await self._queue.dead_letter(
                delivery,
                reason=code,
                failed_at=now,
            )
            return WorkerOutcome.DEAD_LETTERED

        delay = self._retry_base_delay * (2 ** (attempt - 1))
        retry_at = now + delay
        changed = await self._repository.schedule_retry(
            run.id,
            attempt=attempt,
            error_code=code,
            occurred_at=now,
            retry_at=retry_at,
        )
        if not changed:
            await self._queue.ack(delivery)
            return WorkerOutcome.STALE_ATTEMPT

        await self._queue.retry(delivery, available_at=retry_at)
        return WorkerOutcome.RETRY_SCHEDULED
