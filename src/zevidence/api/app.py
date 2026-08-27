"""FastAPI application factory."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from zevidence.api.routes import router
from zevidence.api.schemas import ErrorDetail, ErrorResponse
from zevidence.application import (
    DocumentOwnershipConflict,
    DocumentStateConflict,
    IdempotencyConflict,
    InMemoryRepository,
    Repository,
    ResourceNotFound,
)
from zevidence.application.errors import ApplicationError

ERROR_STATUS: dict[type[ApplicationError], int] = {
    ResourceNotFound: status.HTTP_404_NOT_FOUND,
    DocumentOwnershipConflict: status.HTTP_409_CONFLICT,
    DocumentStateConflict: status.HTTP_409_CONFLICT,
    IdempotencyConflict: status.HTTP_409_CONFLICT,
}


def status_for_application_error(error: ApplicationError) -> int:
    for error_type in type(error).__mro__:
        mapped_status = ERROR_STATUS.get(error_type)
        if mapped_status is not None:
            return mapped_status
    return status.HTTP_400_BAD_REQUEST


def create_app(repository: Repository | None = None) -> FastAPI:
    app = FastAPI(title="zEvidence", version="0.1.0")
    app.state.repository = repository or InMemoryRepository()
    app.include_router(router)

    @app.exception_handler(ApplicationError)
    async def handle_application_error(
        _request: Request,
        error: ApplicationError,
    ) -> JSONResponse:
        response = ErrorResponse(error=ErrorDetail(code=error.code, message=str(error)))
        return JSONResponse(
            status_code=status_for_application_error(error),
            content=response.model_dump(mode="json"),
        )

    return app
