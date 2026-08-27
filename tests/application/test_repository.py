import asyncio

import pytest

from tests.fakes import YieldingInMemoryRepository
from zevidence.application import DossierService
from zevidence.domain import Document, DocumentStatus, Dossier

pytestmark = pytest.mark.anyio


async def test_atomic_creation_survives_a_check_then_insert_yield() -> None:
    repository = YieldingInMemoryRepository()
    dossier = Dossier(title="Northstar", requirements=("Has ISO 27001",))
    document = Document(
        dossier_id=dossier.id,
        filename="security.md",
        mime_type="text/markdown",
        content_hash="a" * 64,
        status=DocumentStatus.READY,
    )
    await repository.add_dossier(dossier)
    await repository.add_document(document, "Synthetic security content")
    service = DossierService(repository)

    first, second = await asyncio.gather(
        service.create_run(
            dossier_id=dossier.id,
            document_ids=(document.id,),
            idempotency_key="concurrent-key",
        ),
        service.create_run(
            dossier_id=dossier.id,
            document_ids=(document.id,),
            idempotency_key="concurrent-key",
        ),
    )

    assert first[0].id == second[0].id
    assert sorted([first[1], second[1]]) == [False, True]
