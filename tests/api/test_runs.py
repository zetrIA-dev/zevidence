import asyncio
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from tests.fakes import YieldingInMemoryRepository
from zevidence.api import create_app

pytestmark = pytest.mark.anyio


async def create_dossier(client: AsyncClient, title: str) -> str:
    response = await client.post(
        "/dossiers",
        json={"title": title, "requirements": ["Has ISO 27001"]},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def register_document(client: AsyncClient, dossier_id: str, filename: str) -> str:
    response = await client.post(
        f"/dossiers/{dossier_id}/documents",
        json={
            "filename": filename,
            "mime_type": "text/markdown",
            "content": f"Synthetic content for {filename}",
        },
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def test_run_rejects_document_from_another_dossier(
    client: AsyncClient,
) -> None:
    dossier_a = await create_dossier(client, "Vendor A")
    dossier_b = await create_dossier(client, "Vendor B")
    document_b = await register_document(client, dossier_b, "vendor-b.md")

    response = await client.post(
        f"/dossiers/{dossier_a}/runs",
        headers={"Idempotency-Key": "run-a"},
        json={"document_ids": [document_b]},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "document_ownership_conflict"


async def test_run_rejects_unknown_document(client: AsyncClient) -> None:
    dossier_id = await create_dossier(client, "Vendor A")

    response = await client.post(
        f"/dossiers/{dossier_id}/runs",
        headers={"Idempotency-Key": "missing-document"},
        json={"document_ids": [str(uuid4())]},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_repeated_idempotency_key_returns_same_run(
    client: AsyncClient,
) -> None:
    dossier_id = await create_dossier(client, "Vendor A")
    document_id = await register_document(client, dossier_id, "vendor-a.md")
    request: dict[str, Any] = {
        "headers": {"Idempotency-Key": "stable-key"},
        "json": {"document_ids": [document_id]},
    }

    first = await client.post(f"/dossiers/{dossier_id}/runs", **request)
    replay = await client.post(f"/dossiers/{dossier_id}/runs", **request)

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.headers["Idempotent-Replayed"] == "true"
    assert replay.json()["id"] == first.json()["id"]


async def test_idempotency_key_rejects_different_payload(
    client: AsyncClient,
) -> None:
    dossier_id = await create_dossier(client, "Vendor A")
    document_a = await register_document(client, dossier_id, "a.md")
    document_b = await register_document(client, dossier_id, "b.md")

    first = await client.post(
        f"/dossiers/{dossier_id}/runs",
        headers={"Idempotency-Key": "stable-key"},
        json={"document_ids": [document_a]},
    )
    conflict = await client.post(
        f"/dossiers/{dossier_id}/runs",
        headers={"Idempotency-Key": "stable-key"},
        json={"document_ids": [document_b]},
    )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"


async def test_missing_idempotency_key_is_a_schema_error(
    client: AsyncClient,
) -> None:
    dossier_id = await create_dossier(client, "Vendor A")
    document_id = await register_document(client, dossier_id, "a.md")

    response = await client.post(
        f"/dossiers/{dossier_id}/runs",
        json={"document_ids": [document_id]},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == [
        "header",
        "Idempotency-Key",
    ]


async def test_run_bounds_document_count(client: AsyncClient) -> None:
    dossier_id = await create_dossier(client, "Vendor A")

    response = await client.post(
        f"/dossiers/{dossier_id}/runs",
        headers={"Idempotency-Key": "too-many-documents"},
        json={"document_ids": [str(uuid4()) for _ in range(101)]},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "too_long"


async def test_concurrent_retries_create_one_run(client: AsyncClient) -> None:
    transport = ASGITransport(app=create_app(YieldingInMemoryRepository()))
    async with AsyncClient(transport=transport, base_url="http://test") as race_client:
        dossier_id = await create_dossier(race_client, "Vendor A")
        document_id = await register_document(race_client, dossier_id, "a.md")

        first, second = await asyncio.gather(
            race_client.post(
                f"/dossiers/{dossier_id}/runs",
                headers={"Idempotency-Key": "concurrent-key"},
                json={"document_ids": [document_id]},
            ),
            race_client.post(
                f"/dossiers/{dossier_id}/runs",
                headers={"Idempotency-Key": "concurrent-key"},
                json={"document_ids": [document_id]},
            ),
        )

    assert sorted([first.status_code, second.status_code]) == [200, 201]
    assert first.json()["id"] == second.json()["id"]


async def test_get_run_returns_created_run(client: AsyncClient) -> None:
    dossier_id = await create_dossier(client, "Vendor A")
    document_id = await register_document(client, dossier_id, "a.md")
    created = await client.post(
        f"/dossiers/{dossier_id}/runs",
        headers={"Idempotency-Key": "get-run"},
        json={"document_ids": [document_id]},
    )

    response = await client.get(f"/runs/{created.json()['id']}")

    assert response.status_code == 200
    assert response.json() == created.json()


async def test_get_unknown_run_returns_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/runs/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_concurrent_requests_do_not_mix_dossiers(
    client: AsyncClient,
) -> None:
    dossier_ids: list[str] = []
    document_ids: list[str] = []
    for title in ("Vendor A", "Vendor B"):
        dossier_id = await create_dossier(client, title)
        document_id = await register_document(client, dossier_id, f"{title}.md")
        dossier_ids.append(dossier_id)
        document_ids.append(document_id)

    run_a, run_b = await asyncio.gather(
        *(
            client.post(
                f"/dossiers/{dossier_id}/runs",
                headers={"Idempotency-Key": "same-key-different-dossier"},
                json={"document_ids": [document_id]},
            )
            for dossier_id, document_id in zip(dossier_ids, document_ids, strict=True)
        )
    )

    assert run_a.status_code == 201
    assert run_b.status_code == 201
    assert run_a.json()["id"] != run_b.json()["id"]
    assert {run_a.json()["dossier_id"], run_b.json()["dossier_id"]} == set(dossier_ids)
