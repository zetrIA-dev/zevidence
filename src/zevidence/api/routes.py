"""HTTP routes for the deterministic application boundary."""

import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

import anyio
from fastapi import APIRouter, Header, Response, status
from fastapi.responses import StreamingResponse

from zevidence.api.dependencies import ServiceDependency
from zevidence.api.schemas import (
    CreateDossierRequest,
    CreateRunRequest,
    DocumentResponse,
    DossierResponse,
    ErrorResponse,
    RegisterDocumentRequest,
    RunEventResponse,
    RunResponse,
)
from zevidence.application.errors import InvalidEventCursor
from zevidence.domain import RunStatus

router = APIRouter()
SSE_HEARTBEAT_SECONDS = 15.0


@router.post(
    "/dossiers",
    response_model=DossierResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dossier(
    payload: CreateDossierRequest,
    service: ServiceDependency,
) -> DossierResponse:
    dossier = await service.create_dossier(
        title=payload.title,
        requirements=payload.requirements,
    )
    return DossierResponse.model_validate(dossier)


@router.get(
    "/dossiers/{dossier_id}",
    response_model=DossierResponse,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
async def get_dossier(
    dossier_id: UUID,
    service: ServiceDependency,
) -> DossierResponse:
    dossier = await service.get_dossier(dossier_id)
    return DossierResponse.model_validate(dossier)


@router.post(
    "/dossiers/{dossier_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
async def register_document(
    dossier_id: UUID,
    payload: RegisterDocumentRequest,
    service: ServiceDependency,
) -> DocumentResponse:
    document = await service.register_document(
        dossier_id=dossier_id,
        filename=payload.filename,
        mime_type=payload.mime_type,
        content=payload.content,
    )
    return DocumentResponse.model_validate(document)


@router.post(
    "/dossiers/{dossier_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_200_OK: {
            "model": RunResponse,
            "description": "Idempotent replay of the original run",
            "headers": {
                "Idempotent-Replayed": {
                    "description": "True when the original run is returned",
                    "schema": {"type": "string", "enum": ["true"]},
                }
            },
        },
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
)
async def create_run(
    dossier_id: UUID,
    payload: CreateRunRequest,
    response: Response,
    service: ServiceDependency,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=200),
    ],
) -> RunResponse:
    run, replayed = await service.create_run(
        dossier_id=dossier_id,
        document_ids=payload.document_ids,
        idempotency_key=idempotency_key,
    )
    if replayed:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotent-Replayed"] = "true"
    return RunResponse.model_validate(run)


@router.get(
    "/runs/{run_id}",
    response_model=RunResponse,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
async def get_run(run_id: UUID, service: ServiceDependency) -> RunResponse:
    run = await service.get_run(run_id)
    return RunResponse.model_validate(run)


@router.get(
    "/runs/{run_id}/events",
    response_class=StreamingResponse,
    responses={
        status.HTTP_200_OK: {
            "content": {"text/event-stream": {}},
            "description": "Ordered replay after Last-Event-ID",
        },
        status.HTTP_204_NO_CONTENT: {
            "description": "Terminal stream already consumed; do not reconnect",
        },
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
async def replay_run_events(
    run_id: UUID,
    service: ServiceDependency,
    last_event_id: Annotated[
        int | None,
        Header(alias="Last-Event-ID", ge=0),
    ] = None,
) -> Response:
    initial_run = await service.get_run(run_id)
    initial_events = await service.get_run_events(
        run_id,
        after_sequence=last_event_id or 0,
    )
    all_events = await service.get_run_events(run_id)
    tail_sequence = all_events[-1].sequence if all_events else 0
    if last_event_id is not None and last_event_id > tail_sequence:
        raise InvalidEventCursor("Last-Event-ID exceeds the run event sequence")
    if (
        initial_run.status in {RunStatus.COMPLETED, RunStatus.FAILED}
        and not initial_events
    ):
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def encode_events() -> AsyncIterator[str]:
        sequence = last_event_id or 0
        while True:
            events = await service.get_run_events(
                run_id,
                after_sequence=sequence,
            )
            for event in events:
                payload = RunEventResponse.model_validate(event).model_dump(mode="json")
                yield (
                    f"id: {event.sequence}\n"
                    f"event: {event.event_type}\n"
                    f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"
                )
                sequence = event.sequence

            run = await service.get_run(run_id)
            if run.status in {RunStatus.COMPLETED, RunStatus.FAILED}:
                trailing_events = await service.get_run_events(
                    run_id,
                    after_sequence=sequence,
                )
                if trailing_events:
                    continue
                return
            with anyio.move_on_after(SSE_HEARTBEAT_SECONDS) as wait_scope:
                await service.wait_for_run_events(
                    run_id,
                    after_sequence=sequence,
                )
            if wait_scope.cancel_called:
                yield ": keep-alive\n\n"

    return StreamingResponse(
        encode_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
