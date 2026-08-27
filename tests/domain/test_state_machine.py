from uuid import uuid4

import pytest

from zevidence.domain import (
    Document,
    DocumentStatus,
    Dossier,
    DossierStatus,
    InvalidStateTransition,
    Run,
    RunStatus,
    transition_document,
    transition_dossier,
    transition_run,
)


def test_dossier_follows_explicit_lifecycle() -> None:
    dossier = Dossier(title="Vendor Alpha", requirements=("Has ISO 27001",))

    ingesting = transition_dossier(dossier, DossierStatus.INGESTING)
    ready = transition_dossier(ingesting, DossierStatus.READY)

    assert dossier.status is DossierStatus.DRAFT
    assert ready.status is DossierStatus.READY


def test_invalid_dossier_transition_fails_explicitly() -> None:
    dossier = Dossier(title="Vendor Alpha", requirements=("Has ISO 27001",))

    with pytest.raises(InvalidStateTransition, match="draft to completed"):
        transition_dossier(dossier, DossierStatus.COMPLETED)


def test_dossier_can_record_and_retry_ingestion_failure() -> None:
    dossier = Dossier(title="Vendor Alpha", requirements=("Has ISO 27001",))
    ingesting = transition_dossier(dossier, DossierStatus.INGESTING)

    failed = transition_dossier(ingesting, DossierStatus.FAILED)
    retrying = transition_dossier(failed, DossierStatus.INGESTING)

    assert failed.status is DossierStatus.FAILED
    assert retrying.status is DossierStatus.INGESTING


def test_run_transitions_to_running_with_start_time() -> None:
    run = Run(
        dossier_id=uuid4(),
        document_ids=(uuid4(),),
        idempotency_key="request-1",
    )

    running = transition_run(run, RunStatus.RUNNING)

    assert running.status is RunStatus.RUNNING
    assert running.started_at is not None


def test_duplicate_run_transition_is_an_idempotent_no_op() -> None:
    run = Run(
        dossier_id=uuid4(),
        document_ids=(uuid4(),),
        idempotency_key="request-1",
    )
    running = transition_run(run, RunStatus.RUNNING)

    duplicate = transition_run(running, RunStatus.RUNNING)

    assert duplicate is running


def test_late_duplicate_after_completion_is_safe_and_visible() -> None:
    run = Run(
        dossier_id=uuid4(),
        document_ids=(uuid4(),),
        idempotency_key="request-1",
    )
    running = transition_run(run, RunStatus.RUNNING)
    completed = transition_run(running, RunStatus.COMPLETED)

    with pytest.raises(InvalidStateTransition, match="completed to running"):
        transition_run(completed, RunStatus.RUNNING)


def test_run_cannot_fail_without_error_details() -> None:
    run = Run(
        dossier_id=uuid4(),
        document_ids=(uuid4(),),
        idempotency_key="request-1",
    )

    with pytest.raises(InvalidStateTransition, match="requires an error"):
        transition_run(run, RunStatus.FAILED)


def test_document_follows_ingestion_lifecycle() -> None:
    document = Document(
        dossier_id=uuid4(),
        filename="security.md",
        mime_type="text/markdown",
        content_hash="a" * 64,
    )

    ingesting = transition_document(document, DocumentStatus.INGESTING)
    ready = transition_document(ingesting, DocumentStatus.READY)

    assert ready.status is DocumentStatus.READY


def test_document_can_retry_after_ingestion_failure() -> None:
    document = Document(
        dossier_id=uuid4(),
        filename="security.md",
        mime_type="text/markdown",
        content_hash="a" * 64,
    )
    ingesting = transition_document(document, DocumentStatus.INGESTING)
    failed = transition_document(ingesting, DocumentStatus.FAILED)

    retrying = transition_document(failed, DocumentStatus.INGESTING)

    assert retrying.status is DocumentStatus.INGESTING


def test_document_rejects_invalid_lifecycle_jump() -> None:
    document = Document(
        dossier_id=uuid4(),
        filename="security.md",
        mime_type="text/markdown",
        content_hash="a" * 64,
    )

    with pytest.raises(InvalidStateTransition, match="pending to ready"):
        transition_document(document, DocumentStatus.READY)
