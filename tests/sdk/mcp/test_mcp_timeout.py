import asyncio
from unittest.mock import MagicMock, patch

import pytest

from openhands.sdk.config.mcp_config import (
    MCPConfig,
    MCPSSEServerConfig,
    MCPStdioServerConfig,
)
from openhands.sdk.mcp.utils import create_mcp_client, create_mcp_tools_from_config


def test_create_mcp_client_sse_connection_timeout():
    """Test SSE connection with timeout."""
    server_config = MCPSSEServerConfig(url="http://unreachable-server:8080")

    with patch("openhands.sdk.mcp.utils.MCPClient") as mock_mcp_client:
        mock_client_instance = MagicMock()
        mock_mcp_client.return_value = mock_client_instance

        # Mock connect_http to timeout
        mock_client_instance.connect_http.side_effect = asyncio.TimeoutError(
            "Connection timeout"
        )

        # Should raise timeout error
        with pytest.raises(asyncio.TimeoutError):
            create_mcp_client(server_config)


def test_create_mcp_client_stdio_connection_timeout():
    """Test stdio connection with timeout."""
    server_config = MCPStdioServerConfig(
        name="timeout_server",
        command="sleep",
        args=["10"],  # Command that takes too long
    )

    with patch("openhands.sdk.mcp.utils.MCPClient") as mock_mcp_client:
        mock_client_instance = MagicMock()
        mock_mcp_client.return_value = mock_client_instance

        # Mock connect_stdio to timeout
        mock_client_instance.connect_stdio.side_effect = asyncio.TimeoutError(
            "Stdio connection timeout"
        )

        # Should raise timeout error
        with pytest.raises(asyncio.TimeoutError):
            create_mcp_client(server_config)


def test_create_mcp_tools_from_config_with_timeout_errors():
    """Test creating MCP tools from configuration with timeout errors."""
    config = MCPConfig(
        sse_servers=[
            MCPSSEServerConfig(url="http://good-server:8080"),
            MCPSSEServerConfig(url="http://timeout-server:8080"),
        ]
    )

    # Mock one successful client and one that times out
    mock_good_client = MagicMock()
    mock_tool = MagicMock()
    mock_tool.name = "tool1"

    def mock_create_client(server_config, conversation_id=None, timeout=None):
        if "timeout-server" in server_config.url:
            raise asyncio.TimeoutError("Connection timeout")
        else:
            return mock_good_client

    with patch(
        "openhands.sdk.mcp.utils.create_mcp_client", side_effect=mock_create_client
    ):
        with patch("openhands.sdk.mcp.utils.MCPToolRegistry") as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry_class.return_value = mock_registry
            mock_registry.get_all_tools.return_value = [mock_tool]

            tools = create_mcp_tools_from_config(config)

            # Should get tools from the good server only
            assert len(tools) == 1
            assert tools[0] == mock_tool
            # Should have only added the successful client
            mock_registry.add_client.assert_called_once_with(
                "http://good-server:8080", mock_good_client
            )


def test_create_mcp_tools_from_config_mixed_timeout_success():
    """Test creating MCP tools with mixed timeout and success results."""
    config = MCPConfig(
        sse_servers=[
            MCPSSEServerConfig(url="http://server1:8080"),
            MCPSSEServerConfig(url="http://server2:8080"),
        ],
        stdio_servers=[
            MCPStdioServerConfig(
                name="stdio1", command="python", args=["-m", "server"]
            ),
            MCPStdioServerConfig(name="stdio2", command="timeout_command"),
        ],
    )

    # Mock clients - some succeed, some timeout
    mock_client = MagicMock()
    mock_tool = MagicMock()
    mock_tool.name = "tool1"

    def mock_create_client(server_config, conversation_id=None, timeout=None):
        if hasattr(server_config, "url") and "server2" in server_config.url:
            raise asyncio.TimeoutError("HTTP timeout")
        elif (
            hasattr(server_config, "command")
            and "timeout_command" in server_config.command
        ):
            raise asyncio.TimeoutError("Stdio timeout")
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


def test_create_mcp_client_with_custom_timeout():
    """Test creating MCP client with custom timeout value."""
    server_config = MCPSSEServerConfig(url="http://server:8080")

    with patch("openhands.sdk.mcp.utils.MCPClient") as mock_mcp_client:
        mock_client_instance = MagicMock()
        mock_mcp_client.return_value = mock_client_instance
        mock_client_instance.connect_http = MagicMock()

        # Test with custom timeout
        create_mcp_client(server_config, timeout=5.0)

        # Verify timeout was passed correctly
        mock_client_instance.connect_http.assert_called_once_with(
            server_config, None, 5.0
        )


def test_create_mcp_tools_from_config_with_custom_timeout():
    """Test creating MCP tools with custom timeout value."""
    config = MCPConfig(sse_servers=[MCPSSEServerConfig(url="http://server:8080")])

    mock_client = MagicMock()
    mock_tool = MagicMock()

    with patch(
        "openhands.sdk.mcp.utils.create_mcp_client", return_value=mock_client
    ) as mock_create:
        with patch("openhands.sdk.mcp.utils.MCPToolRegistry") as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry_class.return_value = mock_registry
            mock_registry.get_all_tools.return_value = [mock_tool]

            # Test with custom timeout
            create_mcp_tools_from_config(config, timeout=10.0)

            # Verify timeout was passed to create_mcp_client
            mock_create.assert_called_with(config.sse_servers[0], None, 10.0)


def test_create_mcp_client_connection_error_vs_timeout():
    """Test distinguishing between connection errors and timeouts."""
    server_config = MCPSSEServerConfig(url="http://server:8080")

    with patch("openhands.sdk.mcp.utils.MCPClient") as mock_mcp_client:
        mock_client_instance = MagicMock()
        mock_mcp_client.return_value = mock_client_instance

        # Test timeout error
        mock_client_instance.connect_http.side_effect = asyncio.TimeoutError("Timeout")
        with pytest.raises(asyncio.TimeoutError):
            create_mcp_client(server_config)

        # Test connection error
        mock_client_instance.connect_http.side_effect = ConnectionError(
            "Connection failed"
        )
        with pytest.raises(ConnectionError):
            create_mcp_client(server_config)
