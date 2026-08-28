import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import anyio
import pytest
from httpx import ASGITransport, AsyncClient, Response

from tests.fakes import CompleteAfterEventSnapshotRepository, ScriptedProcessor
from zevidence.api import create_app
from zevidence.application import (
    ClaimDisposition,
    InMemoryQueue,
    InMemoryRepository,
    OutboxPublisher,
    RunWorker,
)

pytestmark = pytest.mark.anyio


def parse_sse(response: Response) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in response.text.strip().split("\n\n"):
        if not block or block.startswith(":"):
            continue
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append(
            {
                "id": int(fields["id"]),
                "event": fields["event"],
                "data": json.loads(fields["data"]),
            }
        )
    return events


async def create_queued_run(client: AsyncClient) -> str:
    dossier = await client.post(
        "/dossiers",
        json={"title": "Northstar", "requirements": ["Has ISO 27001"]},
    )
    dossier_id = str(dossier.json()["id"])
    document = await client.post(
        f"/dossiers/{dossier_id}/documents",
        json={
            "filename": "security.md",
            "mime_type": "text/markdown",
            "content": "Synthetic security content",
        },
    )
    run = await client.post(
        f"/dossiers/{dossier_id}/runs",
        headers={"Idempotency-Key": "sse-run"},
        json={"document_ids": [document.json()["id"]]},
    )
    return str(run.json()["id"])


async def complete_queued_run(repository: InMemoryRepository) -> None:
    now = datetime.now(UTC) + timedelta(seconds=1)
    queue = InMemoryQueue()
    await OutboxPublisher(repository, queue).publish_pending(published_at=now)
    worker = RunWorker(
        worker_id="worker-a",
        repository=repository,
        queue=queue,
        processor=ScriptedProcessor([None]),
    )
    await worker.process_one(now=now)


async def test_sse_replays_ordered_run_events_after_last_event_id() -> None:
    repository = InMemoryRepository()
    transport = ASGITransport(app=create_app(repository))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_id = await create_queued_run(client)
        await complete_queued_run(repository)

        all_events = await client.get(f"/runs/{run_id}/events")
        resumed = await client.get(
            f"/runs/{run_id}/events",
            headers={"Last-Event-ID": "2"},
        )

    assert all_events.headers["content-type"].startswith("text/event-stream")
    assert [event["id"] for event in parse_sse(all_events)] == [1, 2, 3]
    assert [event["event"] for event in parse_sse(all_events)] == [
        "run_queued",
        "run_started",
        "run_completed",
    ]
    assert [event["id"] for event in parse_sse(resumed)] == [3]


async def test_sse_waits_for_new_events_until_run_is_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("zevidence.api.routes.SSE_HEARTBEAT_SECONDS", 0.005)
    repository = InMemoryRepository()
    transport = ASGITransport(app=create_app(repository))
    responses: list[Response] = []
    response_finished = anyio.Event()
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_id = await create_queued_run(client)

        async def collect_stream() -> None:
            responses.append(await client.get(f"/runs/{run_id}/events"))
            response_finished.set()

        async with anyio.create_task_group() as task_group:
            task_group.start_soon(collect_stream)
            await anyio.sleep(0.01)
            assert not response_finished.is_set()
            await complete_queued_run(repository)

    assert response_finished.is_set()
    assert ": keep-alive\n\n" in responses[0].text
    assert [event["event"] for event in parse_sse(responses[0])] == [
        "run_queued",
        "run_started",
        "run_completed",
    ]


async def test_sse_drains_terminal_event_created_after_event_snapshot() -> None:
    repository = CompleteAfterEventSnapshotRepository()
    transport = ASGITransport(app=create_app(repository))
    now = datetime.now(UTC) + timedelta(seconds=1)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_id = await create_queued_run(client)
        claim = await repository.claim_run(
            UUID(run_id),
            worker_id="worker-a",
            now=now,
            lease_duration=timedelta(seconds=30),
        )
        assert claim.disposition is ClaimDisposition.ACQUIRED
        assert claim.lease is not None
        repository.complete_after_next_event_snapshot(
            run_id=UUID(run_id),
            attempt=claim.lease.attempt,
            occurred_at=now + timedelta(seconds=1),
        )

        response = await client.get(f"/runs/{run_id}/events")

    assert [event["event"] for event in parse_sse(response)] == [
        "run_queued",
        "run_started",
        "run_completed",
    ]


async def test_sse_returns_204_after_terminal_event_was_consumed() -> None:
    repository = InMemoryRepository()
    transport = ASGITransport(app=create_app(repository))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_id = await create_queued_run(client)
        await complete_queued_run(repository)

        response = await client.get(
            f"/runs/{run_id}/events",
            headers={"Last-Event-ID": "3"},
        )

    assert response.status_code == 204
    assert response.content == b""


async def test_sse_rejects_cursor_beyond_event_tail() -> None:
    repository = InMemoryRepository()
    transport = ASGITransport(app=create_app(repository))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_id = await create_queued_run(client)

        response = await client.get(
            f"/runs/{run_id}/events",
            headers={"Last-Event-ID": "999"},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_event_cursor"


async def test_sse_rejects_unknown_run(client: AsyncClient) -> None:
    response = await client.get(f"/runs/{uuid4()}/events")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
