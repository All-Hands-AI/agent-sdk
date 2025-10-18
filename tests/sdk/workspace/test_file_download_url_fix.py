"""Test for the file download URL bug fix (Issue #800).

This test verifies that the _file_download_generator method in RemoteWorkspaceMixin
uses an absolute URL with protocol, not a relative URL.

Before the fix: url was "/api/file/download" (relative, no protocol)
After the fix: url is "{self.host}/api/file/download" (absolute with protocol)
"""

import httpx

from openhands.sdk.workspace.remote.remote_workspace_mixin import RemoteWorkspaceMixin


class TestRemoteWorkspaceMixin(RemoteWorkspaceMixin):
    """Test implementation for testing."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


def test_file_download_generator_uses_absolute_url():
    """Test that _file_download_generator uses absolute URL with http:// protocol.

    This is the core fix for issue #800. When httpx.Client is created without
    a base_url (as it is in RemoteWorkspace), relative URLs like
    "/api/file/download" will fail with UnsupportedProtocol error.

    The fix ensures we always use absolute URLs: "http://host:port/api/file/download"
    """
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000")

    generator = mixin._file_download_generator("/remote/file.txt", "/local/file.txt")

    # Get the request kwargs that will be passed to httpx
    request_kwargs = next(generator)

    # Verify the URL is absolute with protocol
    assert request_kwargs["url"] == "http://localhost:8000/api/file/download"
    assert request_kwargs["method"] == "GET"
    assert request_kwargs["params"]["file_path"] == "/remote/file.txt"

    # Verify it's NOT a relative URL
    assert not request_kwargs["url"].startswith("/")


def test_httpx_client_without_base_url_fails_with_relative_url():
    """Demonstrate that httpx.Client without base_url cannot handle relative URLs.

    This test documents WHY the bug existed - httpx.Client needs either:
    1. A base_url configured on the client, OR
    2. Absolute URLs with protocol in each request

    RemoteWorkspace creates clients without base_url, so we must use absolute URLs.
    """
    # Create a client without base_url (like RemoteWorkspace does)
    client = httpx.Client()

    # This SHOULD raise UnsupportedProtocol with relative URL
    try:
        client.request("GET", "/api/file/download")
        raise AssertionError(
            "Expected UnsupportedProtocol but request somehow succeeded"
        )
    except httpx.UnsupportedProtocol as e:
        # This is expected with relative URL and no base_url
        assert "missing an 'http://' or 'https://' protocol" in str(e)

    client.close()


def test_httpx_client_without_base_url_works_with_absolute_url():
    """Test that httpx.Client can make requests with absolute URL.

    This verifies that when we pass an absolute URL (with http://) to a client
    without base_url, it doesn't raise UnsupportedProtocol error.
    """
    # Create a client without base_url (like RemoteWorkspace does)
    client = httpx.Client()

    # This should NOT raise UnsupportedProtocol
    # We'll let it fail with connection error, which is expected in test
    try:
        client.request("GET", "http://localhost:9999/api/file/download")
    except httpx.ConnectError:
        # Expected - we're not actually running a server
        pass
    except httpx.UnsupportedProtocol:
        # This should NOT happen with absolute URL
        raise AssertionError("UnsupportedProtocol raised with absolute URL")

    client.close()


def test_all_remote_workspace_methods_use_absolute_urls():
    """Verify all RemoteWorkspaceMixin methods use absolute URLs consistently.

    This is a regression test to ensure we don't introduce the same bug in
    other methods.
    """
    mixin = TestRemoteWorkspaceMixin(host="http://localhost:8000")

    # Test execute_command_generator
    cmd_gen = mixin._execute_command_generator("echo test", None, 30.0)
    cmd_kwargs = next(cmd_gen)
    assert cmd_kwargs["url"].startswith("http://")
    assert "http://localhost:8000/api/bash/execute_bash_command" == cmd_kwargs["url"]

    # Test file_upload_generator
    # We need a temporary file for this test
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"test content")
        tmp_path = Path(tmp.name)

    try:
        upload_gen = mixin._file_upload_generator(tmp_path, "/remote/file.txt")
        upload_kwargs = next(upload_gen)
        assert upload_kwargs["url"].startswith("http://")
        assert "http://localhost:8000/api/file/upload" == upload_kwargs["url"]
    finally:
        tmp_path.unlink()

    # Test file_download_generator
    download_gen = mixin._file_download_generator("/remote/file.txt", "/local/file.txt")
    download_kwargs = next(download_gen)
    assert download_kwargs["url"].startswith("http://")
    assert "http://localhost:8000/api/file/download" == download_kwargs["url"]
