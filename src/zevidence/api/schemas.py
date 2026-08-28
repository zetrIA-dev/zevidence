"""HTTP request and response schemas."""

from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from zevidence.domain import DocumentStatus, DossierStatus, RunEventType, RunStatus


class ApiSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )


TrimmedTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
TrimmedRequirement = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
TrimmedFilename = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
TrimmedMimeType = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]


class CreateDossierRequest(ApiSchema):
    title: TrimmedTitle
    requirements: tuple[TrimmedRequirement, ...] = Field(
        min_length=1,
        max_length=100,
    )


class RegisterDocumentRequest(ApiSchema):
    filename: TrimmedFilename
    mime_type: TrimmedMimeType
    content: str = Field(min_length=1, max_length=1_000_000)


class CreateRunRequest(ApiSchema):
    document_ids: tuple[UUID, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def require_unique_documents(self) -> Self:
        if len(set(self.document_ids)) != len(self.document_ids):
            raise ValueError("document_ids must be unique")
        return self


class DossierResponse(ApiSchema):
    id: UUID
    title: str
    requirements: tuple[str, ...]
    status: DossierStatus
    version: int
    created_at: datetime


class DocumentResponse(ApiSchema):
    id: UUID
    dossier_id: UUID
    filename: str
    mime_type: str
    content_hash: str
    status: DocumentStatus
    created_at: datetime


class RunResponse(ApiSchema):
    id: UUID
    dossier_id: UUID
    document_ids: tuple[UUID, ...]
    idempotency_key: str
    status: RunStatus
    started_at: datetime | None
    completed_at: datetime | None


class RunEventResponse(ApiSchema):
    id: UUID
    run_id: UUID
    sequence: int
    event_type: RunEventType
    occurred_at: datetime
    attempt: int | None
    error_code: str | None


class ErrorDetail(ApiSchema):
    code: str
    message: str


class ErrorResponse(ApiSchema):
    error: ErrorDetail
