"""Request-scoped application service for dossier workflows."""

from hashlib import sha256
from uuid import UUID

from zevidence.application.errors import (
    DocumentOwnershipConflict,
    DocumentStateConflict,
    ResourceNotFound,
)
from zevidence.application.repository import Repository
from zevidence.domain import (
    Document,
    DocumentStatus,
    Dossier,
    Run,
    transition_document,
)


class DossierService:
    """Coordinate domain models without storing request-local mutable state."""

    def __init__(self, repository: Repository) -> None:
        self._repository = repository

    async def create_dossier(
        self, *, title: str, requirements: tuple[str, ...]
    ) -> Dossier:
        dossier = Dossier(title=title, requirements=requirements)
        await self._repository.add_dossier(dossier)
        return dossier

    async def get_dossier(self, dossier_id: UUID) -> Dossier:
        dossier = await self._repository.get_dossier(dossier_id)
        if dossier is None:
            raise ResourceNotFound(f"dossier {dossier_id} was not found")
        return dossier

    async def register_document(
        self,
        *,
        dossier_id: UUID,
        filename: str,
        mime_type: str,
        content: str,
    ) -> Document:
        """Store exact content and complete deterministic in-memory ingestion."""
        await self.get_dossier(dossier_id)
        document = Document(
            dossier_id=dossier_id,
            filename=filename,
            mime_type=mime_type,
            content_hash=sha256(content.encode()).hexdigest(),
        )
        document = transition_document(document, DocumentStatus.INGESTING)
        document = transition_document(document, DocumentStatus.READY)
        await self._repository.add_document(document, content)
        return document

    async def create_run(
        self,
        *,
        dossier_id: UUID,
        document_ids: tuple[UUID, ...],
        idempotency_key: str,
    ) -> tuple[Run, bool]:
        await self.get_dossier(dossier_id)
        canonical_ids = tuple(sorted(document_ids, key=str))

        for document_id in canonical_ids:
            document = await self._repository.get_document(document_id)
            if document is None:
                raise ResourceNotFound(f"document {document_id} was not found")
            if document.dossier_id != dossier_id:
                raise DocumentOwnershipConflict(
                    f"document {document_id} belongs to another dossier"
                )
            if document.status is not DocumentStatus.READY:
                raise DocumentStateConflict(
                    f"document {document_id} has not completed ingestion"
                )

        run = Run(
            dossier_id=dossier_id,
            document_ids=canonical_ids,
            idempotency_key=idempotency_key,
        )
        return await self._repository.create_run_once(run)

    async def get_run(self, run_id: UUID) -> Run:
        run = await self._repository.get_run(run_id)
        if run is None:
            raise ResourceNotFound(f"run {run_id} was not found")
        return run
