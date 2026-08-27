"""Cross-entity validation for the claim-to-source trust contract."""

from collections.abc import Mapping
from hashlib import sha256
from uuid import UUID

from zevidence.domain.errors import TraceabilityError
from zevidence.domain.models import (
    Claim,
    Document,
    DocumentStatus,
    Dossier,
    Evidence,
    Run,
    SourceLocator,
)


def _resolve_excerpt(content: str, locator: SourceLocator, excerpt: str) -> bool:
    return content[locator.start_offset : locator.end_offset] == excerpt


def validate_claim_traceability(
    claim: Claim,
    *,
    run: Run,
    dossier: Dossier,
    evidence_by_id: Mapping[UUID, Evidence],
    document_by_id: Mapping[UUID, Document],
    content_by_document_id: Mapping[UUID, str],
) -> None:
    """Prove that every claim citation resolves inside the same dossier and run."""

    if claim.run_id != run.id:
        raise TraceabilityError("claim does not belong to the supplied run")
    if run.dossier_id != dossier.id:
        raise TraceabilityError("run does not belong to the supplied dossier")

    for evidence_id in claim.evidence_ids:
        evidence = evidence_by_id.get(evidence_id)
        if evidence is None:
            raise TraceabilityError(f"evidence {evidence_id} does not exist")

        document = document_by_id.get(evidence.document_id)
        if document is None:
            raise TraceabilityError(f"document {evidence.document_id} does not exist")
        if document.id not in run.document_ids:
            raise TraceabilityError("evidence document was not part of the run")
        if document.dossier_id != dossier.id:
            raise TraceabilityError("evidence document belongs to another dossier")
        if document.status is not DocumentStatus.READY:
            raise TraceabilityError("evidence document has not completed ingestion")

        content = content_by_document_id.get(document.id)
        if content is None:
            raise TraceabilityError("source document content is unavailable")
        if sha256(content.encode()).hexdigest() != document.content_hash:
            raise TraceabilityError("source document hash does not match its content")
        if not _resolve_excerpt(content, evidence.source_locator, evidence.excerpt):
            raise TraceabilityError("evidence locator does not resolve to its excerpt")
        if sha256(evidence.excerpt.encode()).hexdigest() != evidence.content_hash:
            raise TraceabilityError("evidence hash does not match its excerpt")
