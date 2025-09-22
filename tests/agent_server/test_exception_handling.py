"""Test exception handling in the agent server API."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from openhands.agent_server.api import api


@pytest.fixture
def client():
    """Create a test client for the API."""
    return TestClient(api)


def test_http_exception_handler_401():
    """Test that 401 HTTPExceptions are handled cleanly."""
    import json
    from unittest.mock import Mock

    from fastapi import Request

    from openhands.agent_server.api import _http_exception_handler

    # Mock request
    request = Mock(spec=Request)
    request.method = "GET"
    request.url.path = "/"

    # Test 401 error
    exc = HTTPException(
        status_code=401,
        detail="Unauthorized: Invalid or missing X-Session-API-Key header",
    )

    # This should be handled as a client error (not logged as error)
    import asyncio

    response = asyncio.run(_http_exception_handler(request, exc))

    assert response.status_code == 401
    # Parse the JSON response body
    body_content = (
        bytes(response.body).decode()
        if isinstance(response.body, memoryview)
        else response.body.decode()
    )
    json_response = json.loads(body_content)
    assert (
        json_response["detail"]
        == "Unauthorized: Invalid or missing X-Session-API-Key header"
    )


def test_http_exception_handler_500():
    """Test that 500 HTTPExceptions are handled with error logging."""
    # This test would require mocking an endpoint that raises a 500 error
    # For now, we'll just test the handler function directly
    from unittest.mock import Mock

    from fastapi import Request

    from openhands.agent_server.api import _http_exception_handler

    # Mock request
    request = Mock(spec=Request)
    request.method = "GET"
    request.url.path = "/test"

    # Test 500 error
    exc = HTTPException(status_code=500, detail="Internal error")

    # This should be handled as a server error
    import asyncio

    response = asyncio.run(_http_exception_handler(request, exc))

    assert response.status_code == 500
    body_content = (
        bytes(response.body).decode()
        if isinstance(response.body, memoryview)
        else response.body.decode()
    )
    assert "Internal Server Error" in body_content


def test_http_exception_handler_400():
    """Test that 400 HTTPExceptions are handled cleanly."""
    import json
    from unittest.mock import Mock

    from fastapi import Request

    from openhands.agent_server.api import _http_exception_handler

    # Mock request
    request = Mock(spec=Request)
    request.method = "GET"
    request.url.path = "/test"

    # Test 400 error
    exc = HTTPException(status_code=400, detail="Bad request")

    # This should be handled as a client error
    import asyncio

    response = asyncio.run(_http_exception_handler(request, exc))

    assert response.status_code == 400
    # Parse the JSON response body
    body_content = (
        bytes(response.body).decode()
        if isinstance(response.body, memoryview)
        else response.body.decode()
    )
    json_response = json.loads(body_content)
    assert json_response["detail"] == "Bad request"


def test_exception_group_handling():
    """Test that HTTPExceptions wrapped in ExceptionGroups are handled correctly."""
    import json
    from unittest.mock import Mock

    from fastapi import Request

    from openhands.agent_server.api import _unhandled_exception_handler

    # Mock request
    request = Mock(spec=Request)
    request.method = "GET"
    request.url.path = "/test"

    # Create a mock ExceptionGroup with an HTTPException
    class MockExceptionGroup(Exception):
        def __init__(self, message, exceptions):
            super().__init__(message)
            self.exceptions = exceptions

    http_exc = HTTPException(status_code=401, detail="Unauthorized")
    exc_group = MockExceptionGroup("unhandled errors", [http_exc])

    # This should detect the HTTPException and handle it properly
    import asyncio

    response = asyncio.run(_unhandled_exception_handler(request, exc_group))

    assert response.status_code == 401
    # Parse the JSON response body
    body_content = (
        bytes(response.body).decode()
        if isinstance(response.body, memoryview)
        else response.body.decode()
    )
    json_response = json.loads(body_content)
    assert json_response["detail"] == "Unauthorized"
