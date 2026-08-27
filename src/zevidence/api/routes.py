"""HTTP routes for the deterministic application boundary."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Response, status

from zevidence.api.dependencies import ServiceDependency
from zevidence.api.schemas import (
    CreateDossierRequest,
    CreateRunRequest,
    DocumentResponse,
    DossierResponse,
    ErrorResponse,
    RegisterDocumentRequest,
    RunResponse,
)

router = APIRouter()


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
