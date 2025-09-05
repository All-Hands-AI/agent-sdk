import asyncio
from unittest.mock import MagicMock, patch

import pytest

from openhands.sdk.config.mcp_config import (
    MCPConfig,
    MCPSHTTPServerConfig,
    MCPSSEServerConfig,
    MCPStdioServerConfig,
)
from openhands.sdk.mcp.utils import create_mcp_client, create_mcp_tools_from_config


def test_create_mcp_client_invalid_url():
    """Test creating MCP client with invalid URL."""
    # Use a valid URL format but mock the connection to fail
    server_config = MCPSSEServerConfig(url="http://invalid-url-format")

    with patch("openhands.sdk.mcp.utils.MCPClient") as mock_mcp_client:
        mock_client_instance = MagicMock()
        mock_mcp_client.return_value = mock_client_instance

        # Mock connect_http to fail for invalid URL
        mock_client_instance.connect_http.side_effect = ValueError("Invalid URL")

        with pytest.raises(ValueError):
            create_mcp_client(server_config)


def test_create_mcp_client_unreachable_host():
    """Test creating MCP client with unreachable host."""
    server_config = MCPSSEServerConfig(url="http://unreachable-host:8080")

    with patch("openhands.sdk.mcp.utils.MCPClient") as mock_mcp_client:
        mock_client_instance = MagicMock()
        mock_mcp_client.return_value = mock_client_instance

        # Mock connect_http to fail with connection error
        mock_client_instance.connect_http.side_effect = ConnectionError(
            "Host unreachable"
        )

        with pytest.raises(ConnectionError):
            create_mcp_client(server_config)


def test_create_mcp_client_stdio_command_not_found():
    """Test creating MCP stdio client with non-existent command."""
    server_config = MCPStdioServerConfig(
        name="bad_server",
        command="nonexistent_command",
        args=["--help"],
    )

    with patch("openhands.sdk.mcp.utils.MCPClient") as mock_mcp_client:
        mock_client_instance = MagicMock()
        mock_mcp_client.return_value = mock_client_instance

        # Mock connect_stdio to fail for nonexistent command
        mock_client_instance.connect_stdio.side_effect = FileNotFoundError(
            "Command not found"
        )

        with pytest.raises(FileNotFoundError):
            create_mcp_client(server_config)


def test_create_mcp_tools_from_config_mixed_failures():
    """Test creating MCP tools with mixed connection failures."""
    config = MCPConfig(
        sse_servers=[
            MCPSSEServerConfig(url="http://good-sse:8080"),
            MCPSSEServerConfig(url="http://bad-sse:8080"),
        ],
        stdio_servers=[
            MCPStdioServerConfig(
                name="good_stdio",
                command="python",
                args=["-m", "good_stdio"],
            ),
            MCPStdioServerConfig(
                name="bad_stdio",
                command="bad_command",
            ),
        ],
    )

    # Mock clients - some succeed, some fail
    mock_client = MagicMock()
    mock_tool = MagicMock()
    mock_tool.name = "tool1"

    def mock_create_client(server_config, conversation_id=None, timeout=None):
        if hasattr(server_config, "url") and "bad-sse" in server_config.url:
            raise ConnectionError("SSE connection failed")
        elif (
            hasattr(server_config, "command") and "bad_command" in server_config.command
        ):
            raise FileNotFoundError("Stdio command not found")
        else:
            return mock_client

    with patch(
        "openhands.sdk.mcp.utils.create_mcp_client", side_effect=mock_create_client
    ):
        with patch("openhands.sdk.mcp.utils.MCPToolRegistry") as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry_class.return_value = mock_registry
            mock_registry.get_all_tools.return_value = [mock_tool]

            tools = create_mcp_tools_from_config(config)

            # Should get tools from successful servers only (2 out of 4)
            assert len(tools) == 1
            assert (
                mock_registry.add_client.call_count == 2
            )  # Only successful connections


def test_create_mcp_tools_from_config_all_timeout():
    """Test creating MCP tools where all connections timeout."""
    config = MCPConfig(
        sse_servers=[
            MCPSSEServerConfig(url="http://timeout1:8080"),
            MCPSSEServerConfig(url="http://timeout2:8080"),
        ],
        stdio_servers=[
            MCPStdioServerConfig(name="timeout3", command="timeout_cmd1"),
            MCPStdioServerConfig(name="timeout4", command="timeout_cmd2"),
        ],
    )

    # Mock all connections to timeout
    def mock_create_client(server_config, conversation_id=None, timeout=None):
        raise asyncio.TimeoutError("Connection timeout")

    with patch(
        "openhands.sdk.mcp.utils.create_mcp_client", side_effect=mock_create_client
    ):
        with patch("openhands.sdk.mcp.utils.MCPToolRegistry") as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry_class.return_value = mock_registry
            mock_registry.get_all_tools.return_value = []

            tools = create_mcp_tools_from_config(config)

            # Should get no tools due to all timeouts
            assert len(tools) == 0
            assert mock_registry.add_client.call_count == 0  # No successful connections


def test_create_mcp_client_with_various_timeouts():
    """Test creating MCP client with various timeout scenarios."""
    server_config = MCPSSEServerConfig(url="http://server:8080")

    with patch("openhands.sdk.mcp.utils.MCPClient") as mock_mcp_client:
        mock_client_instance = MagicMock()
        mock_mcp_client.return_value = mock_client_instance

        # Test different timeout values
        timeouts = [1.0, 5.0, 10.0, 30.0]

        for timeout_val in timeouts:
            mock_client_instance.connect_http = MagicMock()
            create_mcp_client(server_config, timeout=timeout_val)

            # Verify timeout was passed correctly
            mock_client_instance.connect_http.assert_called_with(
                server_config, None, timeout_val
            )


def test_create_mcp_tools_from_config_partial_success():
    """Test creating MCP tools with partial success across different server types."""
    config = MCPConfig(
        sse_servers=[
            MCPSSEServerConfig(url="http://working-sse:8080"),
            MCPSSEServerConfig(url="http://failing-sse:8080"),
        ],
        stdio_servers=[
            MCPStdioServerConfig(
                name="working_stdio", command="python", args=["-m", "server"]
            ),
        ],
        shttp_servers=[
            MCPSHTTPServerConfig(url="http://working-shttp:8080"),
        ],
    )

    # Mock mixed success/failure
    mock_client = MagicMock()
    mock_tool1 = MagicMock()
    mock_tool1.name = "tool1"
    mock_tool2 = MagicMock()
    mock_tool2.name = "tool2"

    def mock_create_client(server_config, conversation_id=None, timeout=None):
        if hasattr(server_config, "url") and "failing-sse" in server_config.url:
            raise ConnectionError("Failed SSE connection")
        else:
            return mock_client

    with patch(
        "openhands.sdk.mcp.utils.create_mcp_client", side_effect=mock_create_client
    ):
        with patch("openhands.sdk.mcp.utils.MCPToolRegistry") as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry_class.return_value = mock_registry
            mock_registry.get_all_tools.return_value = [mock_tool1, mock_tool2]

            tools = create_mcp_tools_from_config(config)

            # Should get tools from successful servers (3 out of 4)
            assert len(tools) == 2
            assert mock_registry.add_client.call_count == 3  # 3 successful connections


def test_create_mcp_client_stdio_with_timeout():
    """Test creating MCP stdio client with timeout parameter."""
    server_config = MCPStdioServerConfig(
        name="test_server",
        command="python",
        args=["-m", "test_server"],
    )

    with patch("openhands.sdk.mcp.utils.MCPClient") as mock_mcp_client:
        mock_client_instance = MagicMock()
        mock_mcp_client.return_value = mock_client_instance
        mock_client_instance.connect_stdio = MagicMock()

        # Test with custom timeout
        create_mcp_client(server_config, timeout=15.0)

        # Verify timeout was passed correctly
        mock_client_instance.connect_stdio.assert_called_once_with(server_config, 15.0)
