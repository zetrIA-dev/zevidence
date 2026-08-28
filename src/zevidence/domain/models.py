"""Core domain models for the deterministic zEvidence workflow."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DomainModel(BaseModel):
    """Base configuration shared by domain contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class DossierStatus(StrEnum):
    DRAFT = "draft"
    INGESTING = "ingesting"
    READY = "ready"
    REVIEW_REQUIRED = "review_required"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentStatus(StrEnum):
    PENDING = "pending"
    INGESTING = "ingesting"
    READY = "ready"
    FAILED = "failed"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_SCHEDULED = "retry_scheduled"
    COMPLETED = "completed"
    FAILED = "failed"


class RunEventType(StrEnum):
    QUEUED = "run_queued"
    STARTED = "run_started"
    RECLAIMED = "run_reclaimed"
    RETRY_SCHEDULED = "retry_scheduled"
    COMPLETED = "run_completed"
    FAILED = "run_failed"
    DEAD_LETTERED = "run_dead_lettered"


class ClaimStatus(StrEnum):
    SUPPORTED = "supported"
    CONFLICTING = "conflicting"
    UNSUPPORTED = "unsupported"


class Dossier(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=200)
    requirements: tuple[str, ...] = Field(min_length=1)
    status: DossierStatus = DossierStatus.DRAFT
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Document(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    dossier_id: UUID
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=100)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: DocumentStatus = DocumentStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RunError(DomainModel):
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1)


class Run(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    dossier_id: UUID
    document_ids: tuple[UUID, ...] = Field(min_length=1)
    idempotency_key: str = Field(min_length=1, max_length=200)
    status: RunStatus = RunStatus.QUEUED
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: RunError | None = None

    @model_validator(mode="after")
    def validate_terminal_state(self) -> Self:
        if len(set(self.document_ids)) != len(self.document_ids):
            raise ValueError("document_ids must be unique")
        if self.status is RunStatus.FAILED and self.error is None:
            raise ValueError("failed run must record an error")
        if self.status is RunStatus.COMPLETED and self.completed_at is None:
            raise ValueError("completed run must record completed_at")
        if self.status not in {RunStatus.COMPLETED, RunStatus.FAILED}:
            if self.completed_at is not None:
                raise ValueError("non-terminal run cannot record completed_at")
            if self.error is not None:
                raise ValueError("non-failed run cannot record an error")
        return self


class JobMessage(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    schema_version: Literal["1.0"] = "1.0"
    enqueued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OutboxRecord(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    message: JobMessage
    published_at: datetime | None = None


class RunLease(DomainModel):
    run_id: UUID
    worker_id: str = Field(min_length=1, max_length=100)
    attempt: int = Field(ge=1)
    expires_at: datetime


class RunEvent(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    sequence: int = Field(ge=1)
    event_type: RunEventType
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    attempt: int | None = Field(default=None, ge=1)
    error_code: str | None = Field(default=None, min_length=1, max_length=100)


class SourceLocator(DomainModel):
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    page: int | None = Field(default=None, ge=1)
    section: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_offset_range(self) -> Self:
        if self.end_offset <= self.start_offset:
            raise ValueError("end_offset must be greater than start_offset")
        if self.page is None and self.section is None:
            raise ValueError("source locator requires a page or section")
        return self


class Evidence(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    excerpt: str = Field(min_length=1)
    source_locator: SourceLocator
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class Claim(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    text: str = Field(min_length=1)
    status: ClaimStatus
    evidence_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def validate_evidence_contract(self) -> Self:
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence_ids must be unique")
        if (
            self.status in {ClaimStatus.SUPPORTED, ClaimStatus.CONFLICTING}
            and not self.evidence_ids
        ):
            raise ValueError(f"{self.status} claim requires evidence")
        if self.status is ClaimStatus.UNSUPPORTED and self.evidence_ids:
            raise ValueError("unsupported claim cannot reference evidence")
        return self
