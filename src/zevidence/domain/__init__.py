"""Domain contracts for dossiers, runs, claims, and evidence."""

from zevidence.domain.errors import InvalidStateTransition, TraceabilityError
from zevidence.domain.models import (
    Claim,
    ClaimStatus,
    Document,
    DocumentStatus,
    Dossier,
    DossierStatus,
    Evidence,
    Run,
    RunError,
    RunStatus,
    SourceLocator,
)
from zevidence.domain.state_machine import (
    transition_document,
    transition_dossier,
    transition_run,
)
from zevidence.domain.traceability import validate_claim_traceability

__all__ = [
    "Claim",
    "ClaimStatus",
    "Document",
    "DocumentStatus",
    "Dossier",
    "DossierStatus",
    "Evidence",
    "InvalidStateTransition",
    "Run",
    "RunError",
    "RunStatus",
    "SourceLocator",
    "TraceabilityError",
    "transition_document",
    "transition_dossier",
    "transition_run",
    "validate_claim_traceability",
]
