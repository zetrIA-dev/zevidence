from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from zevidence.domain import (
    Claim,
    ClaimStatus,
    Run,
    RunError,
    RunStatus,
    SourceLocator,
)


def test_run_requires_at_least_one_document() -> None:
    with pytest.raises(ValidationError, match="at least 1 item"):
        Run(dossier_id=uuid4(), document_ids=(), idempotency_key="request-1")


def test_supported_claim_requires_evidence() -> None:
    with pytest.raises(ValidationError, match="supported claim requires evidence"):
        Claim(
            run_id=uuid4(),
            text="Vendor is certified",
            status=ClaimStatus.SUPPORTED,
        )


def test_unsupported_claim_rejects_evidence() -> None:
    with pytest.raises(ValidationError, match="cannot reference evidence"):
        Claim(
            run_id=uuid4(),
            text="Vendor is certified",
            status=ClaimStatus.UNSUPPORTED,
            evidence_ids=(uuid4(),),
        )


def test_failed_run_requires_structured_error() -> None:
    with pytest.raises(ValidationError, match="failed run must record an error"):
        Run(
            dossier_id=uuid4(),
            document_ids=(uuid4(),),
            idempotency_key="request-1",
            status=RunStatus.FAILED,
            completed_at=datetime.now(UTC),
        )


def test_failed_run_records_structured_error() -> None:
    run = Run(
        dossier_id=uuid4(),
        document_ids=(uuid4(),),
        idempotency_key="request-1",
        status=RunStatus.FAILED,
        completed_at=datetime.now(UTC),
        error=RunError(code="database_unavailable", message="timeout"),
    )

    assert run.error is not None
    assert run.error.code == "database_unavailable"


def test_claim_status_is_serialized_as_contract_value() -> None:
    claim = Claim(
        run_id=uuid4(),
        text="Vendor is certified",
        status=ClaimStatus.SUPPORTED,
        evidence_ids=(uuid4(),),
    )

    assert claim.model_dump(mode="json")["status"] == "supported"


def test_domain_models_cannot_bypass_invariants_through_mutation() -> None:
    run = Run(
        dossier_id=uuid4(),
        document_ids=(uuid4(),),
        idempotency_key="request-1",
    )
    claim = Claim(
        run_id=run.id,
        text="Vendor is certified",
        status=ClaimStatus.SUPPORTED,
        evidence_ids=(uuid4(),),
    )

    with pytest.raises(ValidationError, match="Instance is frozen"):
        run.status = RunStatus.FAILED
    with pytest.raises(ValidationError, match="Instance is frozen"):
        claim.evidence_ids = ()


def test_source_locator_requires_human_location_metadata() -> None:
    with pytest.raises(ValidationError, match="requires a page or section"):
        SourceLocator(start_offset=10, end_offset=20)
