"""Domain-specific errors."""


class InvalidStateTransition(ValueError):
    """Raised when an entity cannot move between two lifecycle states."""


class TraceabilityError(ValueError):
    """Raised when a claim cannot be traced to its dossier source material."""
