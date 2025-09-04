"""Test MCP config merging functionality."""

import pytest

from openhands.sdk.config import MCPConfig
from openhands.sdk.config.mcp_config import (
    MCPSHTTPServerConfig,
    MCPSSEServerConfig,
    MCPStdioServerConfig,
)


def test_mcp_config_merge_empty():
    """Test merging empty MCP configs."""
    config1 = MCPConfig()
    config2 = MCPConfig()

    merged = config1.merge(config2)

    assert merged.sse_servers == []
    assert merged.stdio_servers == []
    assert merged.shttp_servers == []


def test_mcp_config_merge_sse_servers():
    """Test merging MCP configs with SSE servers."""
    config1 = MCPConfig(
        sse_servers=[
            MCPSSEServerConfig(url="http://server1:8080"),
            MCPSSEServerConfig(url="http://server2:8080", api_key="key1"),
        ]
    )

    config2 = MCPConfig(
        sse_servers=[
            MCPSSEServerConfig(url="http://server3:8080"),
            MCPSSEServerConfig(url="http://server4:8080", api_key="key2"),
        ]
    )

    merged = config1.merge(config2)

    assert len(merged.sse_servers) == 4
    assert merged.sse_servers[0].url == "http://server1:8080"
    assert merged.sse_servers[1].url == "http://server2:8080"
    assert merged.sse_servers[1].api_key == "key1"
    assert merged.sse_servers[2].url == "http://server3:8080"
    assert merged.sse_servers[3].url == "http://server4:8080"
    assert merged.sse_servers[3].api_key == "key2"


def test_mcp_config_merge_stdio_servers():
    """Test merging MCP configs with stdio servers."""
    config1 = MCPConfig(
        stdio_servers=[
            MCPStdioServerConfig(name="server1", command="python"),
            MCPStdioServerConfig(name="server2", command="node", args=["app.js"]),
        ]
    )

    config2 = MCPConfig(
        stdio_servers=[
            MCPStdioServerConfig(
                name="server3", command="java", args=["-jar", "app.jar"]
            ),
            MCPStdioServerConfig(
                name="server4", command="go", env={"GO_ENV": "production"}
            ),
        ]
    )

    merged = config1.merge(config2)

    assert len(merged.stdio_servers) == 4
    assert merged.stdio_servers[0].name == "server1"
    assert merged.stdio_servers[0].command == "python"
    assert merged.stdio_servers[1].name == "server2"
    assert merged.stdio_servers[1].command == "node"
    assert merged.stdio_servers[1].args == ["app.js"]
    assert merged.stdio_servers[2].name == "server3"
    assert merged.stdio_servers[2].command == "java"
    assert merged.stdio_servers[2].args == ["-jar", "app.jar"]
    assert merged.stdio_servers[3].name == "server4"
    assert merged.stdio_servers[3].command == "go"
    assert merged.stdio_servers[3].env == {"GO_ENV": "production"}


def test_mcp_config_merge_shttp_servers():
    """Test merging MCP configs with SHTTP servers."""
    config1 = MCPConfig(
        shttp_servers=[
            MCPSHTTPServerConfig(url="http://server1:8080"),
            MCPSHTTPServerConfig(url="http://server2:8080", api_key="key1"),
        ]
    )

    config2 = MCPConfig(
        shttp_servers=[
            MCPSHTTPServerConfig(url="http://server3:8080"),
            MCPSHTTPServerConfig(url="http://server4:8080", api_key="key2"),
        ]
    )

    merged = config1.merge(config2)

    assert len(merged.shttp_servers) == 4
    assert merged.shttp_servers[0].url == "http://server1:8080"
    assert merged.shttp_servers[1].url == "http://server2:8080"
    assert merged.shttp_servers[1].api_key == "key1"
    assert merged.shttp_servers[2].url == "http://server3:8080"
    assert merged.shttp_servers[3].url == "http://server4:8080"
    assert merged.shttp_servers[3].api_key == "key2"


def test_mcp_config_merge_all_server_types():
    """Test merging MCP configs with all server types."""
    config1 = MCPConfig(
        sse_servers=[MCPSSEServerConfig(url="http://sse1:8080")],
        stdio_servers=[MCPStdioServerConfig(name="stdio1", command="python")],
        shttp_servers=[MCPSHTTPServerConfig(url="http://shttp1:8080")],
    )

    config2 = MCPConfig(
        sse_servers=[MCPSSEServerConfig(url="http://sse2:8080")],
        stdio_servers=[MCPStdioServerConfig(name="stdio2", command="node")],
        shttp_servers=[MCPSHTTPServerConfig(url="http://shttp2:8080")],
    )

    merged = config1.merge(config2)

    assert len(merged.sse_servers) == 2
    assert len(merged.stdio_servers) == 2
    assert len(merged.shttp_servers) == 2

    assert merged.sse_servers[0].url == "http://sse1:8080"
    assert merged.sse_servers[1].url == "http://sse2:8080"

    assert merged.stdio_servers[0].name == "stdio1"
    assert merged.stdio_servers[1].name == "stdio2"

    assert merged.shttp_servers[0].url == "http://shttp1:8080"
    assert merged.shttp_servers[1].url == "http://shttp2:8080"


def test_mcp_config_merge_one_empty():
    """Test merging when one config is empty."""
    config1 = MCPConfig(
        sse_servers=[MCPSSEServerConfig(url="http://server1:8080")],
        stdio_servers=[MCPStdioServerConfig(name="server1", command="python")],
        shttp_servers=[MCPSHTTPServerConfig(url="http://shttp1:8080")],
    )

    config2 = MCPConfig()

    merged = config1.merge(config2)

    assert len(merged.sse_servers) == 1
    assert len(merged.stdio_servers) == 1
    assert len(merged.shttp_servers) == 1
    assert merged.sse_servers[0].url == "http://server1:8080"
    assert merged.stdio_servers[0].name == "server1"
    assert merged.shttp_servers[0].url == "http://shttp1:8080"

    # Test the other way around
    merged2 = config2.merge(config1)

    assert len(merged2.sse_servers) == 1
    assert len(merged2.stdio_servers) == 1
    assert len(merged2.shttp_servers) == 1
    assert merged2.sse_servers[0].url == "http://server1:8080"
    assert merged2.stdio_servers[0].name == "server1"
    assert merged2.shttp_servers[0].url == "http://shttp1:8080"


def test_mcp_config_merge_preserves_original():
    """Test that merging preserves original configs."""
    config1 = MCPConfig(
        sse_servers=[MCPSSEServerConfig(url="http://server1:8080")],
    )

    config2 = MCPConfig(
        sse_servers=[MCPSSEServerConfig(url="http://server2:8080")],
    )

    merged = config1.merge(config2)

    # Original configs should be unchanged
    assert len(config1.sse_servers) == 1
    assert len(config2.sse_servers) == 1
    assert config1.sse_servers[0].url == "http://server1:8080"
    assert config2.sse_servers[0].url == "http://server2:8080"

    # Merged config should have both
    assert len(merged.sse_servers) == 2
    assert merged.sse_servers[0].url == "http://server1:8080"
    assert merged.sse_servers[1].url == "http://server2:8080"


def test_mcp_config_merge_complex_scenario():
    """Test merging with a complex scenario involving different server configs."""
    config1 = MCPConfig(
        sse_servers=[
            MCPSSEServerConfig(url="http://sse1:8080", api_key="sse-key1"),
            MCPSSEServerConfig(url="http://sse2:8080"),
        ],
        stdio_servers=[
            MCPStdioServerConfig(
                name="stdio1",
                command="python",
                args=["-m", "server"],
                env={"DEBUG": "true"},
            ),
        ],
    )

    config2 = MCPConfig(
        sse_servers=[
            MCPSSEServerConfig(url="http://sse3:8080"),
        ],
        stdio_servers=[
            MCPStdioServerConfig(
                name="stdio2",
                command="node",
                args=["server.js", "--port", "3000"],
                env={"NODE_ENV": "production", "PORT": "3000"},
            ),
        ],
        shttp_servers=[
            MCPSHTTPServerConfig(url="http://shttp1:8080", api_key="shttp-key1"),
        ],
    )

    merged = config1.merge(config2)

    # Check SSE servers
    assert len(merged.sse_servers) == 3
    assert merged.sse_servers[0].url == "http://sse1:8080"
    assert merged.sse_servers[0].api_key == "sse-key1"
    assert merged.sse_servers[1].url == "http://sse2:8080"
    assert merged.sse_servers[1].api_key is None
    assert merged.sse_servers[2].url == "http://sse3:8080"
    assert merged.sse_servers[2].api_key is None

    # Check stdio servers
    assert len(merged.stdio_servers) == 2
    assert merged.stdio_servers[0].name == "stdio1"
    assert merged.stdio_servers[0].command == "python"
    assert merged.stdio_servers[0].args == ["-m", "server"]
    assert merged.stdio_servers[0].env == {"DEBUG": "true"}
    assert merged.stdio_servers[1].name == "stdio2"
    assert merged.stdio_servers[1].command == "node"
    assert merged.stdio_servers[1].args == ["server.js", "--port", "3000"]
    assert merged.stdio_servers[1].env == {"NODE_ENV": "production", "PORT": "3000"}

    # Check SHTTP servers
    assert len(merged.shttp_servers) == 1
    assert merged.shttp_servers[0].url == "http://shttp1:8080"
    assert merged.shttp_servers[0].api_key == "shttp-key1"


def test_mcp_config_merge_validation_on_merged_config():
    """Test that validate_servers() works correctly on merged configurations."""
    config1 = MCPConfig(sse_servers=[MCPSSEServerConfig(url="http://server1:8080")])

    config2 = MCPConfig(
        sse_servers=[MCPSSEServerConfig(url="http://server1:8080")]  # Same URL
    )

    merged = config1.merge(config2)

    # The merged config should have duplicate URLs and validation should fail
    with pytest.raises(ValueError, match="Duplicate MCP server URLs are not allowed"):
        merged.validate_servers()
