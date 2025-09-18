"""Tests for MCP utils functionality with new simplified implementation."""

from unittest.mock import MagicMock, patch

from openhands.sdk.mcp import create_mcp_tools


def test_mock_create_mcp_tools_empty_config():
    """Test creating MCP tools with empty configuration."""
    config = {}

    # Mock the MCPClient and its methods
    with patch("openhands.sdk.mcp.utils.MCPClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock call_async_from_sync to return empty list
        mock_client.call_async_from_sync.return_value = []

        tools = create_mcp_tools(config)

        assert len(tools) == 0


def test_mock_create_mcp_tools_stdio_server():
    """Test creating MCP tools with stdio server configuration."""
    config = {
        "mcpServers": {
            "stdio_server": {
                "transport": "stdio",
                "command": "python",
                "args": ["./server.py"],
                "env": {"DEBUG": "true"},
                "cwd": "/path/to/server",
            }
        }
    }

    # Mock the MCPClient and its methods
    with patch("openhands.sdk.mcp.utils.MCPClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock tool
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"

        # Mock call_async_from_sync to return the tools
        mock_client.call_async_from_sync.return_value = [mock_tool]

        tools = create_mcp_tools(config)

        assert len(tools) == 1
        assert tools[0] == mock_tool


def test_mock_create_mcp_tools_http_server():
    """Test creating MCP tools with HTTP server configuration."""
    config = {
        "mcpServers": {
            "http_server": {
                "transport": "http",
                "url": "https://api.example.com/mcp",
                "headers": {"Authorization": "Bearer token"},
                "auth": "oauth",
            }
        }
    }

    # Mock the MCPClient and its methods
    with patch("openhands.sdk.mcp.utils.MCPClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock tool
        mock_tool = MagicMock()
        mock_tool.name = "http_tool"

        # Mock call_async_from_sync to return the tools
        mock_client.call_async_from_sync.return_value = [mock_tool]

        tools = create_mcp_tools(config)

        assert len(tools) == 1
        assert tools[0] == mock_tool


def test_mock_create_mcp_tools_mixed_servers():
    """Test creating MCP tools with mixed server configurations."""
    config = {
        "mcpServers": {
            "stdio_server": {
                "transport": "stdio",
                "command": "python",
                "args": ["./server.py"],
            },
            "http_server": {
                "transport": "http",
                "url": "https://api.example.com/mcp",
            },
        }
    }

    # Mock the MCPClient and its methods
    with patch("openhands.sdk.mcp.utils.MCPClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock tools
        mock_tool1 = MagicMock()
        mock_tool1.name = "stdio_tool"
        mock_tool2 = MagicMock()
        mock_tool2.name = "http_tool"

        # Mock call_async_from_sync to return the tools
        mock_client.call_async_from_sync.return_value = [mock_tool1, mock_tool2]

        tools = create_mcp_tools(config)

        assert len(tools) == 2
        assert tools[0] == mock_tool1
        assert tools[1] == mock_tool2


def test_mock_create_mcp_tools_with_timeout():
    """Test creating MCP tools with custom timeout."""
    config = {
        "mcpServers": {
            "test_server": {
                "transport": "stdio",
                "command": "python",
                "args": ["./server.py"],
            }
        }
    }

    # Mock the MCPClient and its methods
    with patch("openhands.sdk.mcp.utils.MCPClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock call_async_from_sync to return empty list
        mock_client.call_async_from_sync.return_value = []

        tools = create_mcp_tools(config, timeout=60.0)

        # Verify timeout was passed to call_async_from_sync
        mock_client.call_async_from_sync.assert_called_once()
        call_args = mock_client.call_async_from_sync.call_args
        assert call_args.kwargs.get("timeout") == 60.0

        assert len(tools) == 0


def test_mock_create_mcp_tools_connection_error():
    """Test creating MCP tools with connection error."""
    config = {
        "mcpServers": {
            "failing_server": {
                "transport": "stdio",
                "command": "nonexistent_command",
            }
        }
    }

    # Mock the MCPClient and its methods
    with patch("openhands.sdk.mcp.utils.MCPClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock call_async_from_sync to return empty list (connection
        # error handled internally)
        mock_client.call_async_from_sync.return_value = []

        # Should not raise exception, but return empty list
        tools = create_mcp_tools(config)

        assert len(tools) == 0


def test_mock_create_mcp_tools_dict_config():
    """Test creating MCP tools with dict configuration (not MCPConfig object)."""
    config = {
        "mcpServers": {
            "test_server": {
                "transport": "stdio",
                "command": "python",
                "args": ["./server.py"],
            }
        }
    }

    # Mock the MCPClient and its methods
    with patch("openhands.sdk.mcp.utils.MCPClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock tool
        mock_tool = MagicMock()
        mock_tool.name = "dict_tool"

        # Mock call_async_from_sync to return the tools
        mock_client.call_async_from_sync.return_value = [mock_tool]

        tools = create_mcp_tools(config)

        assert len(tools) == 1
        assert tools[0] == mock_tool


def test_real_create_mcp_tools_dict_config():
    """Test creating MCP tools with dict configuration (not MCPConfig object)."""
    mcp_config = {
        "mcpServers": {"fetch": {"command": "uvx", "args": ["mcp-server-fetch"]}}
    }

    tools = create_mcp_tools(mcp_config)
    assert len(tools) == 1
    assert tools[0].name == "fetch"
    input_schema = tools[0].action_type.to_mcp_schema()

    assert "type" in input_schema
    assert input_schema["type"] == "object"
    assert "properties" in input_schema
    assert "url" in input_schema["properties"]
    assert input_schema["properties"]["url"]["type"] == "string"
    assert "required" in input_schema
    assert "url" in input_schema["required"]

    # security_risk should NOT be in the schema when no security analyzer is enabled
    assert "security_risk" not in input_schema["required"]
    assert "security_risk" not in input_schema["properties"]

    mcp_tool = tools[0].to_mcp_tool()
    assert mcp_tool["inputSchema"] == input_schema

    openai_tool = tools[0].to_openai_tool()
    assert openai_tool["type"] == "function"
    assert "parameters" in openai_tool["function"]
    parameters = openai_tool["function"]["parameters"]
    assert "url" in parameters["properties"]
    assert parameters["properties"]["url"]["type"] == "string"
    assert "required" in parameters
    assert "url" in parameters["required"]
    assert openai_tool["function"]["name"] == "fetch"

    # security_risk should NOT be in the OpenAI tool schema when no security analyzer is enabled  # noqa: E501
    assert "security_risk" not in parameters["required"]
    assert "security_risk" not in parameters["properties"]

    assert tools[0].executor is not None
