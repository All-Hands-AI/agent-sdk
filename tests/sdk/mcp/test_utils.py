from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openhands.sdk.config.mcp_config import (
    MCPConfig,
    MCPSHTTPServerConfig,
    MCPSSEServerConfig,
    MCPStdioServerConfig,
)
from openhands.sdk.mcp.utils import create_mcp_client, create_mcp_tools_from_config


class TestCreateMCPClient:
    """Test create_mcp_client function."""

    @pytest.mark.asyncio
    async def test_create_mcp_client_stdio(self):
        """Test creating MCP client with stdio configuration."""
        config = MCPStdioServerConfig(
            name="test_server",
            command="python",
            args=["-m", "test_server"],
            env={"TEST": "value"},
        )

        with patch("openhands.sdk.mcp.utils.MCPClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            client = await create_mcp_client(config)

            assert client == mock_client
            mock_client.connect_stdio.assert_called_once_with(config, 30.0)

    @pytest.mark.asyncio
    async def test_create_mcp_client_sse(self):
        """Test creating MCP client with SSE configuration."""
        config = MCPSSEServerConfig(url="http://localhost:8000/sse", api_key="token")

        with patch("openhands.sdk.mcp.utils.MCPClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            client = await create_mcp_client(config)

            assert client == mock_client
            mock_client.connect_http.assert_called_once_with(config, None, 30.0)

    @pytest.mark.asyncio
    async def test_create_mcp_client_shttp(self):
        """Test creating MCP client with SHTTP configuration."""
        config = MCPSHTTPServerConfig(
            url="http://localhost:8000/shttp", api_key="token"
        )

        with patch("openhands.sdk.mcp.utils.MCPClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            client = await create_mcp_client(config)

            assert client == mock_client
            mock_client.connect_http.assert_called_once_with(config, None, 30.0)

    @pytest.mark.asyncio
    async def test_create_mcp_client_with_timeout(self):
        """Test creating MCP client with custom timeout."""
        config = MCPSSEServerConfig(url="http://localhost:8000/sse")

        with patch("openhands.sdk.mcp.utils.MCPClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            client = await create_mcp_client(config, timeout=10.0)

            assert client == mock_client
            mock_client.connect_http.assert_called_once_with(config, None, 10.0)

    @pytest.mark.asyncio
    async def test_create_mcp_client_with_conversation_id(self):
        """Test creating MCP client with conversation ID."""
        config = MCPSSEServerConfig(url="http://localhost:8000/sse")

        with patch("openhands.sdk.mcp.utils.MCPClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            client = await create_mcp_client(config, conversation_id="test-conv-123")

            assert client == mock_client
            mock_client.connect_http.assert_called_once_with(
                config, "test-conv-123", 30.0
            )

    @pytest.mark.asyncio
    async def test_create_mcp_client_invalid_config(self):
        """Test creating MCP client with invalid configuration."""
        config = MagicMock()  # Invalid config type

        with pytest.raises(ValueError, match="Unsupported server config type"):
            await create_mcp_client(config)

    @pytest.mark.asyncio
    async def test_create_mcp_client_connection_failure(self):
        """Test creating MCP client with connection failure."""
        config = MCPSSEServerConfig(url="http://unreachable:8000/sse")

        with patch("openhands.sdk.mcp.utils.MCPClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.connect_http.side_effect = ConnectionError("Connection failed")

            with pytest.raises(ConnectionError):
                await create_mcp_client(config)


class TestCreateMCPToolsFromConfig:
    """Test create_mcp_tools_from_config function."""

    @pytest.mark.asyncio
    async def test_create_mcp_tools_from_config_empty(self):
        """Test creating MCP tools from empty configuration."""
        config = MCPConfig()

        with patch("openhands.sdk.mcp.utils.MCPToolRegistry") as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry_class.return_value = mock_registry
            mock_registry.get_all_tools.return_value = []

            tools = await create_mcp_tools_from_config(config)

            assert len(tools) == 0

    @pytest.mark.asyncio
    async def test_create_mcp_tools_from_config_sse_success(self):
        """Test creating MCP tools from SSE server configuration."""
        config = MCPConfig(
            sse_servers=[MCPSSEServerConfig(url="http://localhost:8000/sse")]
        )

        # Mock client and tools
        mock_client = AsyncMock()
        mock_tool = MagicMock()
        mock_tool.name = "tool1"

        with patch(
            "openhands.sdk.mcp.utils.create_mcp_client", return_value=mock_client
        ):
            with patch(
                "openhands.sdk.mcp.utils.MCPToolRegistry"
            ) as mock_registry_class:
                mock_registry = MagicMock()
                mock_registry_class.return_value = mock_registry
                mock_registry.get_all_tools.return_value = [mock_tool]

                tools = await create_mcp_tools_from_config(config)

                assert len(tools) == 1
                assert tools[0] == mock_tool
                mock_registry.add_client.assert_called_once_with(
                    "http://localhost:8000/sse", mock_client
                )

    @pytest.mark.asyncio
    async def test_create_mcp_tools_from_config_stdio_success(self):
        """Test creating MCP tools from stdio server configuration."""
        config = MCPConfig(
            stdio_servers=[
                MCPStdioServerConfig(
                    name="test_server", command="python", args=["-m", "test_server"]
                )
            ]
        )

        # Mock client and tools
        mock_client = AsyncMock()
        mock_tool = MagicMock()
        mock_tool.name = "tool1"

        with patch(
            "openhands.sdk.mcp.utils.create_mcp_client", return_value=mock_client
        ):
            with patch(
                "openhands.sdk.mcp.utils.MCPToolRegistry"
            ) as mock_registry_class:
                mock_registry = MagicMock()
                mock_registry_class.return_value = mock_registry
                mock_registry.get_all_tools.return_value = [mock_tool]

                tools = await create_mcp_tools_from_config(config)

                assert len(tools) == 1
                assert tools[0] == mock_tool
                mock_registry.add_client.assert_called_once_with(
                    "test_server", mock_client
                )

    @pytest.mark.asyncio
    async def test_create_mcp_tools_from_config_mixed_servers(self):
        """Test creating MCP tools from mixed server configurations."""
        config = MCPConfig(
            sse_servers=[MCPSSEServerConfig(url="http://localhost:8000/sse")],
            stdio_servers=[
                MCPStdioServerConfig(
                    name="stdio_server", command="python", args=["-m", "stdio_server"]
                )
            ],
            shttp_servers=[MCPSHTTPServerConfig(url="http://localhost:8001/shttp")],
        )

        # Mock client and tools
        mock_client = AsyncMock()
        mock_tool1 = MagicMock()
        mock_tool1.name = "tool1"
        mock_tool2 = MagicMock()
        mock_tool2.name = "tool2"

        with patch(
            "openhands.sdk.mcp.utils.create_mcp_client", return_value=mock_client
        ):
            with patch(
                "openhands.sdk.mcp.utils.MCPToolRegistry"
            ) as mock_registry_class:
                mock_registry = MagicMock()
                mock_registry_class.return_value = mock_registry
                mock_registry.get_all_tools.return_value = [mock_tool1, mock_tool2]

                tools = await create_mcp_tools_from_config(config)

                assert len(tools) == 2
                # Should have called add_client for all 3 servers
                assert mock_registry.add_client.call_count == 3

    @pytest.mark.asyncio
    async def test_create_mcp_tools_from_config_with_errors(self):
        """Test creating MCP tools from configuration with some connection errors."""
        config = MCPConfig(
            sse_servers=[
                MCPSSEServerConfig(url="http://good-server:8000/sse"),
                MCPSSEServerConfig(url="http://bad-server:8000/sse"),
            ]
        )

        # Mock one successful client and one that fails
        mock_good_client = AsyncMock()
        mock_tool = MagicMock()
        mock_tool.name = "tool1"

        def mock_create_client(server_config, conversation_id=None, timeout=None):
            if "good-server" in server_config.url:
                return mock_good_client
            else:
                raise Exception("Connection failed")

        with patch(
            "openhands.sdk.mcp.utils.create_mcp_client", side_effect=mock_create_client
        ):
            with patch(
                "openhands.sdk.mcp.utils.MCPToolRegistry"
            ) as mock_registry_class:
                mock_registry = MagicMock()
                mock_registry_class.return_value = mock_registry
                mock_registry.get_all_tools.return_value = [mock_tool]

                tools = await create_mcp_tools_from_config(config)

                # Should get tools from the good server only
                assert len(tools) == 1
                assert tools[0] == mock_tool
                # Should have only added the successful client
                mock_registry.add_client.assert_called_once_with(
                    "http://good-server:8000/sse", mock_good_client
                )

    @pytest.mark.asyncio
    async def test_create_mcp_tools_from_config_with_timeout(self):
        """Test creating MCP tools from configuration with custom timeout."""
        config = MCPConfig(
            sse_servers=[MCPSSEServerConfig(url="http://localhost:8000/sse")]
        )

        mock_client = AsyncMock()
        mock_tool = MagicMock()

        with patch(
            "openhands.sdk.mcp.utils.create_mcp_client", return_value=mock_client
        ) as mock_create:
            with patch(
                "openhands.sdk.mcp.utils.MCPToolRegistry"
            ) as mock_registry_class:
                mock_registry = MagicMock()
                mock_registry_class.return_value = mock_registry
                mock_registry.get_all_tools.return_value = [mock_tool]

                await create_mcp_tools_from_config(config, timeout=15.0)

                # Verify timeout was passed to create_mcp_client
                mock_create.assert_called_with(config.sse_servers[0], None, 15.0)
