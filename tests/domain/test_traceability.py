from hashlib import sha256
from uuid import uuid4

import pytest

from zevidence.domain import (
    Claim,
    ClaimStatus,
    Document,
    DocumentStatus,
    Dossier,
    Evidence,
    Run,
    SourceLocator,
    TraceabilityError,
    validate_claim_traceability,
)


def test_traceability_rejects_invented_evidence_id() -> None:
    dossier = Dossier(title="Vendor Alpha", requirements=("Has certification",))
    document_id = uuid4()
    run = Run(
        dossier_id=dossier.id,
        document_ids=(document_id,),
        idempotency_key="request-1",
    )
    claim = Claim(
        run_id=run.id,
        text="Vendor is certified",
        status=ClaimStatus.SUPPORTED,
        evidence_ids=(uuid4(),),
    )

    with pytest.raises(TraceabilityError, match="does not exist"):
        validate_claim_traceability(
            claim,
            run=run,
            dossier=dossier,
            evidence_by_id={},
            document_by_id={},
            content_by_document_id={},
        )


def test_traceability_rejects_document_outside_run() -> None:
    dossier = Dossier(title="Vendor Alpha", requirements=("Has certification",))
    run = Run(
        dossier_id=dossier.id,
        document_ids=(uuid4(),),
        idempotency_key="request-1",
    )
    content = "Vendor is ISO 27001 certified."
    document = Document(
        dossier_id=dossier.id,
        filename="security.md",
        mime_type="text/markdown",
        content_hash=sha256(content.encode()).hexdigest(),
        status=DocumentStatus.READY,
    )
    evidence = Evidence(
        document_id=document.id,
        excerpt=content,
        source_locator=SourceLocator(
            start_offset=0,
            end_offset=len(content),
            section="Certification",
        ),
        content_hash=sha256(content.encode()).hexdigest(),
    )
    claim = Claim(
        run_id=run.id,
        text="Vendor is certified",
        status=ClaimStatus.SUPPORTED,
        evidence_ids=(evidence.id,),
    )

    with pytest.raises(TraceabilityError, match="was not part of the run"):
        validate_claim_traceability(
            claim,
            run=run,
            dossier=dossier,
            evidence_by_id={evidence.id: evidence},
            document_by_id={document.id: document},
            content_by_document_id={document.id: content},
        )


def test_traceability_rejects_locator_with_wrong_offsets() -> None:
    dossier = Dossier(title="Vendor Alpha", requirements=("Has certification",))
    content = "# Certification\n\nVendor is ISO 27001 certified.\n"
    document = Document(
        dossier_id=dossier.id,
        filename="security.md",
        mime_type="text/markdown",
        content_hash=sha256(content.encode()).hexdigest(),
        status=DocumentStatus.READY,
    )
    run = Run(
        dossier_id=dossier.id,
        document_ids=(document.id,),
        idempotency_key="request-1",
    )
    evidence = Evidence(
        document_id=document.id,
        excerpt="Vendor is ISO 27001 certified.",
        source_locator=SourceLocator(
            start_offset=0,
            end_offset=len("Vendor is ISO 27001 certified."),
            section="Certification",
        ),
        content_hash=sha256(b"Vendor is ISO 27001 certified.").hexdigest(),
    )
    claim = Claim(
        run_id=run.id,
        text="Vendor is certified",
        status=ClaimStatus.SUPPORTED,
        evidence_ids=(evidence.id,),
    )

    with pytest.raises(TraceabilityError, match="locator does not resolve"):
        validate_claim_traceability(
            claim,
            run=run,
            dossier=dossier,
            evidence_by_id={evidence.id: evidence},
            document_by_id={document.id: document},
            content_by_document_id={document.id: content},
        )


def test_traceability_rejects_document_before_ingestion_completes() -> None:
    dossier = Dossier(title="Vendor Alpha", requirements=("Has certification",))
    content = "# Certification\n\nVendor is ISO 27001 certified.\n"
    document = Document(
        dossier_id=dossier.id,
        filename="security.md",
        mime_type="text/markdown",
        content_hash=sha256(content.encode()).hexdigest(),
    )
    run = Run(
        dossier_id=dossier.id,
        document_ids=(document.id,),
        idempotency_key="request-1",
    )
    evidence = Evidence(
        document_id=document.id,
        excerpt="Vendor is ISO 27001 certified.",
        source_locator=SourceLocator(
            start_offset=content.index("Vendor"),
            end_offset=content.index("Vendor") + len("Vendor is ISO 27001 certified."),
            section="Certification",
        ),
        content_hash=sha256(b"Vendor is ISO 27001 certified.").hexdigest(),
    )
    claim = Claim(
        run_id=run.id,
        text="Vendor is certified",
        status=ClaimStatus.SUPPORTED,
        evidence_ids=(evidence.id,),
    )

    with pytest.raises(TraceabilityError, match="not completed ingestion"):
        validate_claim_traceability(
            claim,
            run=run,
            dossier=dossier,
            evidence_by_id={evidence.id: evidence},
            document_by_id={document.id: document},
            content_by_document_id={document.id: content},
        )
