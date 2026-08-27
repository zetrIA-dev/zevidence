from hashlib import sha256
from uuid import uuid4

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def create_dossier(client: AsyncClient, title: str = "Northstar") -> str:
    response = await client.post(
        "/dossiers",
        json={"title": title, "requirements": ["Has ISO 27001"]},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def test_register_document_calculates_integrity_hash(
    client: AsyncClient,
) -> None:
    dossier_id = await create_dossier(client)

    response = await client.post(
        f"/dossiers/{dossier_id}/documents",
        json={
            "filename": "security.md",
            "mime_type": "text/markdown",
            "content": "Vendor is ISO 27001 certified.",
        },
    )

    assert response.status_code == 201
    assert response.json()["dossier_id"] == dossier_id
    assert response.json()["status"] == "ready"
    assert len(response.json()["content_hash"]) == 64
    assert "content" not in response.json()


async def test_document_hash_preserves_submitted_whitespace(
    client: AsyncClient,
) -> None:
    dossier_id = await create_dossier(client)
    content = "  Exact source content.\n"

    response = await client.post(
        f"/dossiers/{dossier_id}/documents",
        json={
            "filename": "source.md",
            "mime_type": "text/markdown",
            "content": content,
        },
    )

    assert response.status_code == 201
    assert response.json()["content_hash"] == sha256(content.encode()).hexdigest()


async def test_register_document_requires_existing_dossier(
    client: AsyncClient,
) -> None:
    response = await client.post(
        f"/dossiers/{uuid4()}/documents",
        json={
            "filename": "security.md",
            "mime_type": "text/markdown",
            "content": "Synthetic content",
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_register_document_bounds_content_size(client: AsyncClient) -> None:
    dossier_id = await create_dossier(client)

    response = await client.post(
        f"/dossiers/{dossier_id}/documents",
        json={
            "filename": "oversized.md",
            "mime_type": "text/markdown",
            "content": "x" * 1_000_001,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "string_too_long"
