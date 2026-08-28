import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from tests.fakes import FailOnceOutboxAckRepository, ScriptedProcessor
from zevidence.application import (
    ClaimDisposition,
    InMemoryQueue,
    InMemoryRepository,
    OutboxPublisher,
    PermanentProcessingError,
    RetryableProcessingError,
    RunWorker,
    WorkerOutcome,
)
from zevidence.application.service import DossierService
from zevidence.domain import JobMessage, Run, RunEventType, RunStatus

pytestmark = pytest.mark.anyio


async def create_queued_run(repository: InMemoryRepository) -> Run:
    service = DossierService(repository)
    dossier = await service.create_dossier(
        title="Northstar",
        requirements=("Has ISO 27001",),
    )
    document = await service.register_document(
        dossier_id=dossier.id,
        filename="security.md",
        mime_type="text/markdown",
        content="Synthetic security content",
    )
    run, replayed = await service.create_run(
        dossier_id=dossier.id,
        document_ids=(document.id,),
        idempotency_key="background-run",
    )
    assert not replayed
    return run


async def publish_run(
    repository: InMemoryRepository,
    queue: InMemoryQueue,
    *,
    now: datetime,
) -> None:
    publisher = OutboxPublisher(repository, queue)
    assert await publisher.publish_pending(published_at=now) == 1


async def test_run_creation_writes_outbox_and_queued_event() -> None:
    repository = InMemoryRepository()
    run = await create_queued_run(repository)

    pending = await repository.list_pending_outbox()
    events = await repository.list_run_events(run.id)

    assert len(pending) == 1
    assert pending[0].message.run_id == run.id
    assert [event.event_type for event in events] == [RunEventType.QUEUED]


async def test_missing_run_message_is_dead_lettered() -> None:
    repository = InMemoryRepository()
    queue = InMemoryQueue()
    processor = ScriptedProcessor([])
    now = datetime.now(UTC)

    await queue.send(JobMessage(run_id=uuid4(), enqueued_at=now))
    worker = RunWorker(
        worker_id="worker-a",
        repository=repository,
        queue=queue,
        processor=processor,
    )

    outcome = await worker.process_one(now=now)

    assert outcome is WorkerOutcome.DEAD_LETTERED
    assert len(await queue.dead_letters()) == 1
    assert processor.processed_run_ids == []


async def test_outbox_ack_failure_redelivers_without_reprocessing_run() -> None:
    repository = FailOnceOutboxAckRepository()
    queue = InMemoryQueue()
    processor = ScriptedProcessor([None])
    run = await create_queued_run(repository)
    now = datetime.now(UTC) + timedelta(seconds=1)
    publisher = OutboxPublisher(repository, queue)

    with pytest.raises(RuntimeError, match="acknowledgement failure"):
        await publisher.publish_pending(published_at=now)
    assert await publisher.publish_pending(published_at=now) == 1
    worker = RunWorker(
        worker_id="worker-a",
        repository=repository,
        queue=queue,
        processor=processor,
    )

    first = await worker.process_one(now=now)
    duplicate = await worker.process_one(now=now)

    assert first is WorkerOutcome.COMPLETED
    assert duplicate is WorkerOutcome.DUPLICATE_IGNORED
    assert processor.processed_run_ids == [run.id]


async def test_unacknowledged_delivery_reappears_after_visibility_timeout() -> None:
    queue = InMemoryQueue(visibility_timeout=timedelta(seconds=10))
    now = datetime.now(UTC)
    message = JobMessage(run_id=uuid4(), enqueued_at=now)
    await queue.send(message)

    first = await queue.receive(now=now)
    hidden = await queue.receive(now=now + timedelta(seconds=9))
    redelivered = await queue.receive(now=now + timedelta(seconds=10))

    assert first is not None
    assert hidden is None
    assert redelivered is not None
    assert redelivered.message.id == message.id
    assert redelivered.receipt_id != first.receipt_id
    assert redelivered.delivery_count == 2


async def test_live_lease_defers_redelivery_instead_of_losing_message() -> None:
    repository = InMemoryRepository()
    queue = InMemoryQueue(visibility_timeout=timedelta(seconds=1))
    processor = ScriptedProcessor([None])
    run = await create_queued_run(repository)
    now = datetime.now(UTC) + timedelta(seconds=1)
    await publish_run(repository, queue, now=now)
    delivery = await queue.receive(now=now)
    assert delivery is not None
    first_claim = await repository.claim_run(
        run.id,
        worker_id="worker-a",
        now=now,
        lease_duration=timedelta(seconds=10),
    )
    assert first_claim.disposition is ClaimDisposition.ACQUIRED
    worker = RunWorker(
        worker_id="worker-b",
        repository=repository,
        queue=queue,
        processor=processor,
        lease_duration=timedelta(seconds=10),
    )

    deferred = await worker.process_one(now=now + timedelta(seconds=1))
    too_early = await worker.process_one(now=now + timedelta(seconds=9))
    recovered = await worker.process_one(now=now + timedelta(seconds=10))

    assert deferred is WorkerOutcome.DEFERRED
    assert too_early is WorkerOutcome.IDLE
    assert recovered is WorkerOutcome.COMPLETED
    assert processor.processed_run_ids == [run.id]


async def test_retry_state_survives_crash_before_queue_retry() -> None:
    repository = InMemoryRepository()
    queue = InMemoryQueue(visibility_timeout=timedelta(seconds=1))
    processor = ScriptedProcessor([None])
    run = await create_queued_run(repository)
    now = datetime.now(UTC) + timedelta(seconds=1)
    retry_at = now + timedelta(seconds=10)
    await publish_run(repository, queue, now=now)
    delivery = await queue.receive(now=now)
    assert delivery is not None
    claim = await repository.claim_run(
        run.id,
        worker_id="crashed-worker",
        now=now,
        lease_duration=timedelta(seconds=1),
    )
    assert claim.lease is not None
    assert await repository.schedule_retry(
        run.id,
        attempt=claim.lease.attempt,
        error_code="provider_timeout",
        occurred_at=now,
        retry_at=retry_at,
    )
    worker = RunWorker(
        worker_id="recovery-worker",
        repository=repository,
        queue=queue,
        processor=processor,
    )

    deferred = await worker.process_one(now=now + timedelta(seconds=1))
    recovered = await worker.process_one(now=retry_at)

    assert deferred is WorkerOutcome.DEFERRED
    assert recovered is WorkerOutcome.COMPLETED
    assert processor.processed_run_ids == [run.id]


async def test_repeated_worker_crashes_exhaust_attempt_budget() -> None:
    repository = InMemoryRepository()
    queue = InMemoryQueue(visibility_timeout=timedelta(seconds=1))
    processor = ScriptedProcessor([])
    run = await create_queued_run(repository)
    now = datetime.now(UTC) + timedelta(seconds=1)
    await publish_run(repository, queue, now=now)

    for offset in range(3):
        crash_time = now + timedelta(seconds=offset)
        delivery = await queue.receive(now=crash_time)
        assert delivery is not None
        claim = await repository.claim_run(
            run.id,
            worker_id=f"crashed-worker-{offset}",
            now=crash_time,
            lease_duration=timedelta(seconds=1),
        )
        assert claim.disposition is ClaimDisposition.ACQUIRED

    worker = RunWorker(
        worker_id="recovery-worker",
        repository=repository,
        queue=queue,
        processor=processor,
        lease_duration=timedelta(seconds=1),
        max_attempts=3,
    )

    outcome = await worker.process_one(now=now + timedelta(seconds=3))

    stored = await repository.get_run(run.id)
    assert outcome is WorkerOutcome.DEAD_LETTERED
    assert stored is not None
    assert stored.status is RunStatus.FAILED
    assert stored.error is not None
    assert stored.error.code == "attempts_exhausted"
    assert processor.processed_run_ids == []


async def test_successful_worker_completes_run_once() -> None:
    repository = InMemoryRepository()
    queue = InMemoryQueue()
    processor = ScriptedProcessor([None])
    run = await create_queued_run(repository)
    now = datetime.now(UTC) + timedelta(seconds=1)
    await publish_run(repository, queue, now=now)
    worker = RunWorker(
        worker_id="worker-a",
        repository=repository,
        queue=queue,
        processor=processor,
    )

    outcome = await worker.process_one(now=now)

    assert outcome is WorkerOutcome.COMPLETED
    stored = await repository.get_run(run.id)
    assert stored is not None
    assert stored.status is RunStatus.COMPLETED
    assert processor.processed_run_ids == [run.id]
    assert [event.event_type for event in await repository.list_run_events(run.id)] == [
        RunEventType.QUEUED,
        RunEventType.STARTED,
        RunEventType.COMPLETED,
    ]


async def test_duplicate_delivery_does_not_repeat_completed_work() -> None:
    repository = InMemoryRepository()
    queue = InMemoryQueue()
    processor = ScriptedProcessor([None])
    run = await create_queued_run(repository)
    now = datetime.now(UTC) + timedelta(seconds=1)
    record = (await repository.list_pending_outbox())[0]
    await publish_run(repository, queue, now=now)
    await queue.send(record.message)
    worker = RunWorker(
        worker_id="worker-a",
        repository=repository,
        queue=queue,
        processor=processor,
    )

    first = await worker.process_one(now=now)
    duplicate = await worker.process_one(now=now)

    assert first is WorkerOutcome.COMPLETED
    assert duplicate is WorkerOutcome.DUPLICATE_IGNORED
    assert processor.processed_run_ids == [run.id]


async def test_retryable_failure_retries_with_backoff_then_completes() -> None:
    repository = InMemoryRepository()
    queue = InMemoryQueue()
    processor = ScriptedProcessor(
        [RetryableProcessingError("provider_timeout", "provider timed out"), None]
    )
    run = await create_queued_run(repository)
    now = datetime.now(UTC) + timedelta(seconds=1)
    await publish_run(repository, queue, now=now)
    worker = RunWorker(
        worker_id="worker-a",
        repository=repository,
        queue=queue,
        processor=processor,
        retry_base_delay=timedelta(seconds=5),
    )

    first = await worker.process_one(now=now)
    too_early = await worker.process_one(now=now + timedelta(seconds=4))
    second = await worker.process_one(now=now + timedelta(seconds=5))

    assert first is WorkerOutcome.RETRY_SCHEDULED
    assert too_early is WorkerOutcome.IDLE
    assert second is WorkerOutcome.COMPLETED
    stored = await repository.get_run(run.id)
    assert stored is not None
    assert stored.status is RunStatus.COMPLETED
    assert [event.event_type for event in await repository.list_run_events(run.id)] == [
        RunEventType.QUEUED,
        RunEventType.STARTED,
        RunEventType.RETRY_SCHEDULED,
        RunEventType.STARTED,
        RunEventType.COMPLETED,
    ]


async def test_duplicate_delivery_cannot_bypass_retry_backoff() -> None:
    repository = InMemoryRepository()
    queue = InMemoryQueue()
    processor = ScriptedProcessor(
        [RetryableProcessingError("provider_timeout", "provider timed out"), None]
    )
    run = await create_queued_run(repository)
    now = datetime.now(UTC) + timedelta(seconds=1)
    record = (await repository.list_pending_outbox())[0]
    await publish_run(repository, queue, now=now)
    await queue.send(record.message)
    worker = RunWorker(
        worker_id="worker-a",
        repository=repository,
        queue=queue,
        processor=processor,
        retry_base_delay=timedelta(seconds=5),
    )

    first = await worker.process_one(now=now)
    duplicate = await worker.process_one(now=now)
    retried = await worker.process_one(now=now + timedelta(seconds=5))

    assert first is WorkerOutcome.RETRY_SCHEDULED
    assert duplicate is WorkerOutcome.DEFERRED
    assert retried is WorkerOutcome.COMPLETED
    assert processor.processed_run_ids == [run.id, run.id]


async def test_permanent_failure_is_not_retried() -> None:
    repository = InMemoryRepository()
    queue = InMemoryQueue()
    processor = ScriptedProcessor(
        [PermanentProcessingError("document_missing", "document does not exist")]
    )
    run = await create_queued_run(repository)
    now = datetime.now(UTC) + timedelta(seconds=1)
    await publish_run(repository, queue, now=now)
    worker = RunWorker(
        worker_id="worker-a",
        repository=repository,
        queue=queue,
        processor=processor,
    )

    outcome = await worker.process_one(now=now)

    stored = await repository.get_run(run.id)
    assert outcome is WorkerOutcome.FAILED
    assert stored is not None
    assert stored.status is RunStatus.FAILED
    assert stored.error is not None
    assert stored.error.code == "document_missing"
    assert await queue.pending() == ()
    assert await queue.dead_letters() == ()


async def test_unexpected_failure_is_logged_and_public_error_is_sanitized(
    caplog: pytest.LogCaptureFixture,
) -> None:
    repository = InMemoryRepository()
    queue = InMemoryQueue()
    processor = ScriptedProcessor([RuntimeError("synthetic processor bug")])
    run = await create_queued_run(repository)
    now = datetime.now(UTC) + timedelta(seconds=1)
    await publish_run(repository, queue, now=now)
    worker = RunWorker(
        worker_id="worker-a",
        repository=repository,
        queue=queue,
        processor=processor,
        max_attempts=1,
    )

    with caplog.at_level(logging.ERROR):
        outcome = await worker.process_one(now=now)

    stored = await repository.get_run(run.id)
    assert outcome is WorkerOutcome.DEAD_LETTERED
    assert stored is not None
    assert stored.error is not None
    assert stored.error.code == "unexpected_processing_error"
    assert stored.error.message == "unexpected processing failure"
    assert "unexpected run processor failure" in caplog.text


async def test_exhausted_retry_moves_message_to_dlq() -> None:
    repository = InMemoryRepository()
    queue = InMemoryQueue()
    processor = ScriptedProcessor(
        [
            RetryableProcessingError("provider_timeout", "first timeout"),
            RetryableProcessingError("provider_timeout", "second timeout"),
        ]
    )
    run = await create_queued_run(repository)
    now = datetime.now(UTC) + timedelta(seconds=1)
    await publish_run(repository, queue, now=now)
    worker = RunWorker(
        worker_id="worker-a",
        repository=repository,
        queue=queue,
        processor=processor,
        retry_base_delay=timedelta(seconds=1),
        max_attempts=2,
    )

    first = await worker.process_one(now=now)
    second = await worker.process_one(now=now + timedelta(seconds=1))

    assert first is WorkerOutcome.RETRY_SCHEDULED
    assert second is WorkerOutcome.DEAD_LETTERED
    stored = await repository.get_run(run.id)
    assert stored is not None
    assert stored.status is RunStatus.FAILED
    assert len(await queue.dead_letters()) == 1
    assert [event.event_type for event in await repository.list_run_events(run.id)][
        -2:
    ] == [RunEventType.FAILED, RunEventType.DEAD_LETTERED]


async def test_expired_lease_is_reclaimed_and_old_attempt_is_fenced() -> None:
    repository = InMemoryRepository()
    run = await create_queued_run(repository)
    now = datetime.now(UTC) + timedelta(seconds=1)
    lease_duration = timedelta(seconds=10)

    first_claim = await repository.claim_run(
        run.id,
        worker_id="worker-a",
        now=now,
        lease_duration=lease_duration,
    )
    second_claim = await repository.claim_run(
        run.id,
        worker_id="worker-b",
        now=now + timedelta(seconds=11),
        lease_duration=lease_duration,
    )

    first = first_claim.lease
    second = second_claim.lease
    assert first is not None
    assert second is not None
    assert second.attempt == 2
    assert not await repository.complete_run(
        run.id,
        attempt=first.attempt,
        occurred_at=now + timedelta(seconds=12),
    )
    assert await repository.complete_run(
        run.id,
        attempt=second.attempt,
        occurred_at=now + timedelta(seconds=12),
    )
    assert [event.event_type for event in await repository.list_run_events(run.id)] == [
        RunEventType.QUEUED,
        RunEventType.STARTED,
        RunEventType.RECLAIMED,
        RunEventType.COMPLETED,
    ]
