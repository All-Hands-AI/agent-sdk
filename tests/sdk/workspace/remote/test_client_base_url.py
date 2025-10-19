"""Test for client base_url configuration (Issue #800).

This test verifies that RemoteWorkspace and AsyncRemoteWorkspace create httpx
clients with the correct base_url set, allowing relative URLs to work properly.

Root cause: RemoteWorkspace/AsyncRemoteWorkspace were creating httpx.Client()
without base_url, causing relative URLs like "/api/file/download" to fail
with UnsupportedProtocol error.

Fix: Clients are now created with base_url=self.host, enabling relative URLs
throughout the codebase.
"""

import httpx

from openhands.sdk.workspace.remote.async_remote_workspace import (
    AsyncRemoteWorkspace,
)
from openhands.sdk.workspace.remote.base import RemoteWorkspace


def test_remote_workspace_client_has_base_url():
    """Test that RemoteWorkspace creates client with base_url."""
    workspace = RemoteWorkspace(host="http://localhost:8000", working_dir="/workspace")

    # Access the client property to trigger lazy initialization
    client = workspace.client

    # Verify it's an httpx.Client
    assert isinstance(client, httpx.Client)

    # Verify base_url is set correctly
    assert client.base_url is not None
    assert str(client.base_url) == "http://localhost:8000"


def test_async_remote_workspace_client_has_base_url():
    """Test that AsyncRemoteWorkspace creates client with base_url."""
    workspace = AsyncRemoteWorkspace(host="http://localhost:8000")

    # Access the client property to trigger lazy initialization
    client = workspace.client

    # Verify it's an httpx.AsyncClient
    assert isinstance(client, httpx.AsyncClient)

    # Verify base_url is set correctly
    assert client.base_url is not None
    assert str(client.base_url) == "http://localhost:8000"


def test_remote_workspace_client_with_trailing_slash():
    """Test that RemoteWorkspace handles host with trailing slash."""
    workspace = RemoteWorkspace(host="http://localhost:8000/", working_dir="/workspace")
    client = workspace.client

    # httpx normalizes the base_url (may remove trailing slash)
    assert client.base_url is not None
    # Either with or without trailing slash is acceptable
    assert str(client.base_url).startswith("http://localhost:8000")


def test_relative_urls_work_with_base_url():
    """Verify that relative URLs work when base_url is set.

    This demonstrates that with base_url configured, httpx can properly
    construct full URLs from relative paths.
    """
    # Create a client with base_url (like our fixed RemoteWorkspace does)
    client = httpx.Client(base_url="http://localhost:8000")

    # Build a request with relative URL
    request = client.build_request("GET", "/api/file/download")

    # Verify the full URL was constructed correctly
    assert str(request.url) == "http://localhost:8000/api/file/download"

    client.close()


def test_relative_urls_fail_without_base_url():
    """Demonstrate that relative URLs fail without base_url.

    This test documents the bug that existed before the fix.
    """
    # Create a client WITHOUT base_url (the old broken behavior)
    client = httpx.Client()

    # Attempting to make a request with relative URL should raise UnsupportedProtocol
    try:
        # Use request() rather than build_request() as that's what triggers the error
        client.request("GET", "/api/file/download")
        raise AssertionError("Expected UnsupportedProtocol but request succeeded")
    except httpx.UnsupportedProtocol as e:
        # This is expected
        assert "missing an 'http://' or 'https://' protocol" in str(e)
    finally:
        client.close()
