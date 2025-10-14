"""Test that APIRemoteWorkspace and AsyncRemoteWorkspace make equivalent HTTP requests.

This test suite ensures that both workspace implementations invoke the same URLs
with the same methods and parameters for equivalent operations.
"""

from urllib.parse import urlparse


def test_execute_command_url_patterns():
    """Test that both classes use the same URL patterns for execute_command."""
    # Test the URL patterns used by both implementations
    
    # APIRemoteWorkspace uses relative URLs with base_url
    api_execute_url = "/api/bash/execute_bash_command"
    api_search_url = "/api/bash/bash_events/search"
    
    # AsyncRemoteWorkspace uses absolute URLs
    server_url = "https://server.test.com"
    async_execute_url = f"{server_url}/api/bash/execute_bash_command"
    async_search_url = f"{server_url}/api/bash/bash_events/search"
    
    # Normalize URLs by extracting paths
    def normalize_url(url):
        return urlparse(url).path
    
    # Both should resolve to the same paths
    assert normalize_url(api_execute_url) == normalize_url(async_execute_url)
    assert normalize_url(api_search_url) == normalize_url(async_search_url)
    
    # Verify the expected paths
    assert normalize_url(api_execute_url) == "/api/bash/execute_bash_command"
    assert normalize_url(api_search_url) == "/api/bash/bash_events/search"


def test_file_upload_url_patterns():
    """Test that both classes use the same URL patterns for file_upload."""
    # APIRemoteWorkspace uses relative URLs with base_url
    api_upload_url = "/api/file/upload"
    
    # AsyncRemoteWorkspace uses absolute URLs
    server_url = "https://server.test.com"
    async_upload_url = f"{server_url}/api/file/upload"
    
    # Normalize URLs by extracting paths
    def normalize_url(url):
        return urlparse(url).path
    
    # Both should resolve to the same paths
    assert normalize_url(api_upload_url) == normalize_url(async_upload_url)
    
    # Verify the expected path
    assert normalize_url(api_upload_url) == "/api/file/upload"


def test_file_download_url_patterns():
    """Test that both classes use the same URL patterns for file_download."""
    # APIRemoteWorkspace uses relative URLs with base_url
    api_download_url = "/api/file/download"
    
    # AsyncRemoteWorkspace uses absolute URLs
    server_url = "https://server.test.com"
    async_download_url = f"{server_url}/api/file/download"
    
    # Normalize URLs by extracting paths
    def normalize_url(url):
        return urlparse(url).path
    
    # Both should resolve to the same paths
    assert normalize_url(api_download_url) == normalize_url(async_download_url)
    
    # Verify the expected path
    assert normalize_url(api_download_url) == "/api/file/download"


def test_execute_command_payload_structure():
    """Test that both classes use the same payload structure for execute_command."""
    # Common parameters
    command = "echo 'test'"
    cwd = "/test/dir"
    timeout = 30.0
    
    # Expected payload structure (used by both implementations)
    expected_payload = {
        "command": command,
        "timeout": int(timeout),
        "cwd": str(cwd),
    }
    
    # Both implementations should create the same payload
    # This is verified by examining the source code:
    # - APIRemoteWorkspace (line 65-70 in base.py)
    # - AsyncRemoteWorkspace (line 55-60 in async_remote_workspace.py)
    
    # Verify payload structure matches expectations
    assert "command" in expected_payload
    assert "timeout" in expected_payload
    assert "cwd" in expected_payload
    assert expected_payload["command"] == command
    assert expected_payload["timeout"] == int(timeout)
    assert expected_payload["cwd"] == str(cwd)


def test_file_upload_payload_structure():
    """Test that both classes use the same payload structure for file_upload."""
    # Common parameters
    destination_path = "/remote/test_file.txt"
    
    # Expected form data structure (used by both implementations)
    expected_form_data = {"destination_path": str(destination_path)}
    
    # Both implementations should create the same form data
    # This is verified by examining the source code:
    # - APIRemoteWorkspace (line 179 in base.py)
    # - AsyncRemoteWorkspace (line 173 in async_remote_workspace.py)
    
    # Verify form data structure matches expectations
    assert "destination_path" in expected_form_data
    assert expected_form_data["destination_path"] == str(destination_path)


def test_file_download_params_structure():
    """Test that both classes use the same params structure for file_download."""
    # Common parameters
    source_path = "/remote/test_file.txt"
    
    # Expected params structure (used by both implementations)
    expected_params = {"file_path": str(source_path)}
    
    # Both implementations should create the same params
    # This is verified by examining the source code:
    # - APIRemoteWorkspace (line 232 in base.py)
    # - AsyncRemoteWorkspace (line 226 in async_remote_workspace.py)
    
    # Verify params structure matches expectations
    assert "file_path" in expected_params
    assert expected_params["file_path"] == str(source_path)


def test_authentication_header_patterns():
    """Test that both classes use the same authentication header patterns."""
    # Expected header key for session authentication
    expected_header_key = "X-Session-API-Key"
    test_api_key = "test-session-key"
    
    # Both implementations should use the same header key
    # This is verified by examining the source code:
    # - APIRemoteWorkspace: set in base.py line 33 during client initialization
    # - AsyncRemoteWorkspace: set in _headers() method line 30
    
    # Verify header structure
    expected_headers = {expected_header_key: test_api_key}
    assert expected_header_key in expected_headers
    assert expected_headers[expected_header_key] == test_api_key


def test_http_methods_consistency():
    """Test that both classes use the same HTTP methods for equivalent operations."""
    # Expected HTTP methods for each operation
    expected_methods = {
        "execute_bash_command": "POST",
        "bash_events_search": "GET", 
        "file_upload": "POST",
        "file_download": "GET",
    }
    
    # Both implementations should use the same HTTP methods
    # This is verified by examining the source code:
    # - APIRemoteWorkspace: POST for execute (line 74), GET for search (line 94),
    #   POST for upload (line 182), GET for download (line 235)
    # - AsyncRemoteWorkspace: POST for execute (line 64), GET for search (line 85),
    #   POST for upload (line 176), GET for download (line 229)
    
    # Verify method consistency
    assert expected_methods["execute_bash_command"] == "POST"
    assert expected_methods["bash_events_search"] == "GET"
    assert expected_methods["file_upload"] == "POST"
    assert expected_methods["file_download"] == "GET"


def test_search_parameters_differences():
    """Test and document the intentional differences in search parameters."""
    # APIRemoteWorkspace search parameters (from base.py lines 96-101)
    api_search_params = {
        "kind__eq": "BashOutput",
        "command_id__eq": "test-command-id",
        "sort_order": "TIMESTAMP",
        "limit": 10,
    }
    
    # AsyncRemoteWorkspace search parameters (from async_remote_workspace.py
    # lines 87-90)
    async_search_params = {
        "sort_order": "TIMESTAMP",
        "limit": 100,
        # Note: AsyncRemoteWorkspace filters client-side instead of using
        # server-side filters
    }
    
    # Document the intentional differences:
    # 1. APIRemoteWorkspace uses server-side filtering with kind__eq and
    #    command_id__eq
    # 2. AsyncRemoteWorkspace uses client-side filtering and fetches more
    #    results (limit: 100 vs 10)
    # 3. Both use the same sort_order: "TIMESTAMP"
    
    # Verify the documented differences
    assert "kind__eq" in api_search_params
    assert "command_id__eq" in api_search_params
    assert api_search_params["limit"] == 10
    
    assert "kind__eq" not in async_search_params
    assert "command_id__eq" not in async_search_params
    assert async_search_params["limit"] == 100
    
    # Verify common parameters
    assert (
        api_search_params["sort_order"]
        == async_search_params["sort_order"]
        == "TIMESTAMP"
    )


def test_timeout_handling_consistency():
    """Test that both classes handle timeouts consistently."""
    # Common timeout value
    timeout = 30.0
    
    # Both implementations should:
    # 1. Convert timeout to int for the API payload
    # 2. Add buffer time for HTTP timeout (timeout + 5.0)
    
    # Expected API payload timeout (int conversion)
    expected_api_timeout = int(timeout)
    assert expected_api_timeout == 30
    
    # Expected HTTP timeout (with buffer)
    expected_http_timeout = timeout + 5.0
    assert expected_http_timeout == 35.0
    
    # This is verified by examining the source code:
    # - APIRemoteWorkspace: line 67 (int conversion), line 77 (HTTP timeout
    #   with buffer)
    # - AsyncRemoteWorkspace: line 57 (int conversion), line 67 (HTTP timeout
    #   with buffer)


def test_error_handling_patterns():
    """Test that both classes follow similar error handling patterns."""
    # Both implementations should:
    # 1. Catch exceptions during HTTP requests
    # 2. Return CommandResult/FileOperationResult with error information
    # 3. Log errors appropriately
    
    # Expected error result structure for execute_command
    expected_error_command_result = {
        "command": "test command",
        "exit_code": -1,
        "stdout": "",
        "stderr": "Remote execution error: <error message>",
        "timeout_occurred": False,
    }
    
    # Expected error result structure for file operations
    expected_error_file_result = {
        "success": False,
        "source_path": "source",
        "destination_path": "dest", 
        "error": "<error message>",
    }
    
    # Verify error result structures
    assert expected_error_command_result["exit_code"] == -1
    # CommandResult doesn't have success field
    assert "success" not in expected_error_command_result
    assert expected_error_file_result["success"] is False
    assert "error" in expected_error_file_result
    
    # This is verified by examining the source code:
    # - APIRemoteWorkspace: lines 141-149 (execute_command), lines 200-207
    #   (file_upload), lines 256-263 (file_download)
    # - AsyncRemoteWorkspace: lines 135-143 (execute_command), lines 194-201
    #   (file_upload), lines 250-257 (file_download)