from fastapi import status

from zevidence.api.app import status_for_application_error
from zevidence.application import ResourceNotFound


class NestedResourceNotFound(ResourceNotFound):
    """Represent a future specialized not-found error."""


def test_specialized_application_error_inherits_http_status() -> None:
    error = NestedResourceNotFound("nested resource was not found")

    assert status_for_application_error(error) == status.HTTP_404_NOT_FOUND
