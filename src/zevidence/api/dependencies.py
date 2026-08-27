"""FastAPI dependency boundaries."""

from typing import Annotated, cast

from fastapi import Depends, Request

from zevidence.application import DossierService, Repository


def get_repository(request: Request) -> Repository:
    return cast(Repository, request.app.state.repository)


def get_service(
    repository: Annotated[Repository, Depends(get_repository)],
) -> DossierService:
    return DossierService(repository)


ServiceDependency = Annotated[DossierService, Depends(get_service)]
