import pytest

from zevidence.application import (
    DocumentStateConflict,
    DossierService,
    InMemoryRepository,
)
from zevidence.domain import Document, Dossier

pytestmark = pytest.mark.anyio


async def test_document_registration_stores_exact_content() -> None:
    repository = InMemoryRepository()
    service = DossierService(repository)
    dossier = await service.create_dossier(
        title="Northstar",
        requirements=("Has ISO 27001",),
    )
    content = "  Exact synthetic content.\n"

    document = await service.register_document(
        dossier_id=dossier.id,
        filename="security.md",
        mime_type="text/markdown",
        content=content,
    )

    assert await repository.get_document_content(document.id) == content


async def test_run_rejects_document_that_has_not_completed_ingestion() -> None:
    repository = InMemoryRepository()
    dossier = Dossier(title="Northstar", requirements=("Has ISO 27001",))
    document = Document(
        dossier_id=dossier.id,
        filename="security.md",
        mime_type="text/markdown",
        content_hash="a" * 64,
    )
    await repository.add_dossier(dossier)
    await repository.add_document(document, "Synthetic security content")
    service = DossierService(repository)

    with pytest.raises(DocumentStateConflict, match="not completed ingestion"):
        await service.create_run(
            dossier_id=dossier.id,
            document_ids=(document.id,),
            idempotency_key="pending-document",
        )
