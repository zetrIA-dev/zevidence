"""Repository contract and deterministic in-memory adapter."""

import asyncio
from typing import Protocol
from uuid import UUID

from zevidence.application.errors import IdempotencyConflict
from zevidence.domain import Document, Dossier, Run


class Repository(Protocol):
    async def add_dossier(self, dossier: Dossier) -> None: ...

    async def get_dossier(self, dossier_id: UUID) -> Dossier | None: ...

    async def add_document(self, document: Document, content: str) -> None: ...

    async def get_document(self, document_id: UUID) -> Document | None: ...

    async def get_document_content(self, document_id: UUID) -> str | None: ...

    async def get_run(self, run_id: UUID) -> Run | None: ...

    async def create_run_once(self, run: Run) -> tuple[Run, bool]: ...


class InMemoryRepository:
    """In-memory adapter with atomic idempotent run creation."""

    def __init__(self) -> None:
        self._dossiers: dict[UUID, Dossier] = {}
        self._documents: dict[UUID, Document] = {}
        self._document_contents: dict[UUID, str] = {}
        self._runs: dict[UUID, Run] = {}
        self._run_keys: dict[tuple[UUID, str], UUID] = {}
        self._run_lock = asyncio.Lock()

    async def add_dossier(self, dossier: Dossier) -> None:
        self._dossiers[dossier.id] = dossier

    async def get_dossier(self, dossier_id: UUID) -> Dossier | None:
        return self._dossiers.get(dossier_id)

    async def add_document(self, document: Document, content: str) -> None:
        self._documents[document.id] = document
        self._document_contents[document.id] = content

    async def get_document(self, document_id: UUID) -> Document | None:
        return self._documents.get(document_id)

    async def get_document_content(self, document_id: UUID) -> str | None:
        return self._document_contents.get(document_id)

    async def get_run(self, run_id: UUID) -> Run | None:
        return self._runs.get(run_id)

    async def _before_run_insert(self) -> None:
        """Allow tests to expose a check-then-insert scheduling boundary."""

    async def create_run_once(self, run: Run) -> tuple[Run, bool]:
        key = (run.dossier_id, run.idempotency_key)
        async with self._run_lock:
            existing_id = self._run_keys.get(key)
            if existing_id is not None:
                existing = self._runs[existing_id]
                if existing.document_ids != run.document_ids:
                    raise IdempotencyConflict(
                        "idempotency key was already used with a different request"
                    )
                return existing, True

            await self._before_run_insert()
            self._runs[run.id] = run
            self._run_keys[key] = run.id
            return run, False
