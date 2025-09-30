"""
Unit tests for dependency-based authentication functionality.
Tests the check_session_api_key dependency with multiple session API keys support.
"""

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from openhands.agent_server.config import Config
from openhands.agent_server.dependencies import (
    create_session_api_key_dependency,
)


def test_create_session_api_key_dependency():
    """Test the dependency factory function."""
    config = Config(session_api_keys=["factory-key"])
    dependency_func = create_session_api_key_dependency(config)

    # Test with valid key
    dependency_func("factory-key")  # Should not raise

    # Test with invalid key
    with pytest.raises(HTTPException) as exc_info:
        dependency_func("invalid-key")
    assert exc_info.value.status_code == 401

    # Test with None when keys are required
    with pytest.raises(HTTPException) as exc_info:
        dependency_func(None)
    assert exc_info.value.status_code == 401


def test_create_session_api_key_dependency_no_keys():
    """Test the dependency factory with no keys configured."""
    config = Config(session_api_keys=[])
    dependency_func = create_session_api_key_dependency(config)

    # Should work with any key or None when no keys are configured
    dependency_func("any-key")  # Should not raise
    dependency_func(None)  # Should not raise


def test_create_session_api_key_dependency_in_fastapi():
    """Test the dependency factory integrated with FastAPI."""
    config = Config(session_api_keys=["factory-test-key"])
    dependency_func = create_session_api_key_dependency(config)

    app = FastAPI()

    @app.get("/test", dependencies=[Depends(dependency_func)])
    async def test_endpoint():
        return {"message": "success"}

    client = TestClient(app, raise_server_exceptions=False)

    # Test without auth
    response = client.get("/test")
    assert response.status_code == 401

    # Test with valid auth
    response = client.get("/test", headers={"X-Session-API-Key": "factory-test-key"})
    assert response.status_code == 200

    # Test with invalid auth
    response = client.get("/test", headers={"X-Session-API-Key": "wrong-key"})
    assert response.status_code == 401
