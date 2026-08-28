"""Application services and repository contracts."""

from zevidence.application.errors import (
    DocumentOwnershipConflict,
    DocumentStateConflict,
    IdempotencyConflict,
    InvalidEventCursor,
    ResourceNotFound,
)
from zevidence.application.queue import (
    DeadLetter,
    InMemoryQueue,
    OutboxPublisher,
    Queue,
    QueueDelivery,
)
from zevidence.application.repository import (
    ClaimDisposition,
    InMemoryRepository,
    Repository,
    RunClaimResult,
)
from zevidence.application.service import DossierService
from zevidence.application.worker import (
    PermanentProcessingError,
    RetryableProcessingError,
    RunProcessor,
    RunWorker,
    WorkerOutcome,
)

__all__ = [
    "DocumentOwnershipConflict",
    "DocumentStateConflict",
    "ClaimDisposition",
    "DossierService",
    "IdempotencyConflict",
    "InvalidEventCursor",
    "InMemoryQueue",
    "InMemoryRepository",
    "OutboxPublisher",
    "PermanentProcessingError",
    "Queue",
    "QueueDelivery",
    "Repository",
    "ResourceNotFound",
    "RetryableProcessingError",
    "RunProcessor",
    "RunClaimResult",
    "RunWorker",
    "WorkerOutcome",
    "DeadLetter",
]
