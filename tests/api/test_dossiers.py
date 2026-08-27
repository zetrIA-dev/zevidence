from uuid import uuid4

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_create_dossier_controls_internal_fields(client: AsyncClient) -> None:
    response = await client.post(
        "/dossiers",
        json={
            "title": "Northstar review",
            "requirements": ["Has ISO 27001"],
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "draft"
    assert response.json()["version"] == 1
    assert response.json()["id"]


async def test_create_dossier_rejects_missing_title(client: AsyncClient) -> None:
    response = await client.post(
        "/dossiers",
        json={"requirements": ["Has ISO 27001"]},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "title"]


async def test_create_dossier_rejects_internal_status_field(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/dossiers",
        json={
            "title": "Northstar review",
            "requirements": ["Has ISO 27001"],
            "status": "completed",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "extra_forbidden"


async def test_create_dossier_bounds_requirement_count(client: AsyncClient) -> None:
    response = await client.post(
        "/dossiers",
        json={
            "title": "Northstar review",
            "requirements": [f"Requirement {index}" for index in range(101)],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "too_long"


async def test_create_dossier_bounds_requirement_length(client: AsyncClient) -> None:
    response = await client.post(
        "/dossiers",
        json={"title": "Northstar review", "requirements": ["x" * 501]},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "string_too_long"


async def test_get_unknown_dossier_returns_stable_error(
    client: AsyncClient,
) -> None:
    dossier_id = uuid4()

    response = await client.get(f"/dossiers/{dossier_id}")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": f"dossier {dossier_id} was not found",
        }
    }
