"""Application-layer errors mapped to transport responses."""


class ApplicationError(Exception):
    """Base error with a stable machine-readable code."""

    code = "application_error"


class ResourceNotFound(ApplicationError):
    code = "not_found"


class DocumentOwnershipConflict(ApplicationError):
    code = "document_ownership_conflict"


class DocumentStateConflict(ApplicationError):
    code = "document_state_conflict"


class IdempotencyConflict(ApplicationError):
    code = "idempotency_conflict"
