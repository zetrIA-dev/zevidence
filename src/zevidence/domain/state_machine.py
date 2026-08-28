"""Explicit lifecycle transitions for deterministic domain entities."""

from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum

from zevidence.domain.errors import InvalidStateTransition
from zevidence.domain.models import (
    Document,
    DocumentStatus,
    Dossier,
    DossierStatus,
    Run,
    RunError,
    RunStatus,
)

DOSSIER_TRANSITIONS: Mapping[DossierStatus, frozenset[DossierStatus]] = {
    DossierStatus.DRAFT: frozenset({DossierStatus.INGESTING}),
    DossierStatus.INGESTING: frozenset({DossierStatus.READY, DossierStatus.FAILED}),
    DossierStatus.READY: frozenset({DossierStatus.REVIEW_REQUIRED}),
    DossierStatus.REVIEW_REQUIRED: frozenset(
        {DossierStatus.READY, DossierStatus.COMPLETED}
    ),
    DossierStatus.COMPLETED: frozenset(),
    DossierStatus.FAILED: frozenset({DossierStatus.INGESTING}),
}

DOCUMENT_TRANSITIONS: Mapping[DocumentStatus, frozenset[DocumentStatus]] = {
    DocumentStatus.PENDING: frozenset({DocumentStatus.INGESTING}),
    DocumentStatus.INGESTING: frozenset({DocumentStatus.READY, DocumentStatus.FAILED}),
    DocumentStatus.READY: frozenset(),
    DocumentStatus.FAILED: frozenset({DocumentStatus.INGESTING}),
}

RUN_TRANSITIONS: Mapping[RunStatus, frozenset[RunStatus]] = {
    RunStatus.QUEUED: frozenset({RunStatus.RUNNING, RunStatus.FAILED}),
    RunStatus.RUNNING: frozenset(
        {RunStatus.RETRY_SCHEDULED, RunStatus.COMPLETED, RunStatus.FAILED}
    ),
    RunStatus.RETRY_SCHEDULED: frozenset({RunStatus.RUNNING, RunStatus.FAILED}),
    RunStatus.COMPLETED: frozenset(),
    RunStatus.FAILED: frozenset(),
}


def _require_transition[StatusT: StrEnum](
    current: StatusT,
    target: StatusT,
    allowed: Mapping[StatusT, frozenset[StatusT]],
) -> None:
    if target not in allowed[current]:
        raise InvalidStateTransition(f"cannot transition from {current} to {target}")


def transition_dossier(dossier: Dossier, target: DossierStatus) -> Dossier:
    _require_transition(dossier.status, target, DOSSIER_TRANSITIONS)
    return Dossier.model_validate({**dossier.model_dump(), "status": target})


def transition_document(document: Document, target: DocumentStatus) -> Document:
    _require_transition(document.status, target, DOCUMENT_TRANSITIONS)
    return Document.model_validate({**document.model_dump(), "status": target})


def transition_run(
    run: Run,
    target: RunStatus,
    *,
    error: RunError | None = None,
    occurred_at: datetime | None = None,
) -> Run:
    if run.status is target:
        return run
    _require_transition(run.status, target, RUN_TRANSITIONS)
    if target is RunStatus.FAILED and error is None:
        raise InvalidStateTransition("transition to failed requires an error")
    timestamp = occurred_at or datetime.now(UTC)
    updates: dict[str, object] = {"status": target}

    if target is RunStatus.RUNNING and run.started_at is None:
        updates["started_at"] = timestamp
    elif target is RunStatus.COMPLETED:
        updates["completed_at"] = timestamp
    elif target is RunStatus.FAILED:
        updates["completed_at"] = timestamp
        updates["error"] = error

    return Run.model_validate({**run.model_dump(), **updates})
