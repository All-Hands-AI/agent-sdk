import pytest
from pydantic import ValidationError

from openhands.sdk.config import MCPConfig
from openhands.sdk.config.mcp_config import (
    MCPSHTTPServerConfig,
    MCPSSEServerConfig,
    MCPStdioServerConfig,
)


def test_mcp_sse_server_config_basic():
    """Test basic MCPSSEServerConfig."""
    config = MCPSSEServerConfig(url="http://server1:8080")
    assert config.url == "http://server1:8080"
    assert config.api_key is None


def test_mcp_sse_server_config_with_api_key():
    """Test MCPSSEServerConfig with API key."""
    config = MCPSSEServerConfig(url="http://server1:8080", api_key="test-api-key")
    assert config.url == "http://server1:8080"
    assert config.api_key == "test-api-key"


def test_mcp_sse_server_config_invalid_url():
    """Test MCPSSEServerConfig with invalid URL format."""
    with pytest.raises(ValidationError) as exc_info:
        MCPSSEServerConfig(url="not_a_url")
    assert "URL must include a scheme" in str(exc_info.value)


def test_mcp_sse_server_config_empty_url():
    """Test MCPSSEServerConfig with empty URL."""
    with pytest.raises(ValidationError) as exc_info:
        MCPSSEServerConfig(url="")
    assert "URL cannot be empty" in str(exc_info.value)


def test_mcp_sse_server_config_valid_schemes():
    """Test MCPSSEServerConfig with various valid URL schemes."""
    valid_urls = [
        "http://server1:8080",
        "https://server1:8080",
        "ws://server1:8080",
        "wss://server1:8080",
    ]

    for url in valid_urls:
        config = MCPSSEServerConfig(url=url)
        assert config.url == url


def test_mcp_sse_server_config_invalid_schemes():
    """Test MCPSSEServerConfig with invalid URL schemes."""
    invalid_urls = [
        "ftp://server1:8080",
        "file://server1:8080",
        "tcp://server1:8080",
    ]

    for url in invalid_urls:
        with pytest.raises(ValidationError) as exc_info:
            MCPSSEServerConfig(url=url)
        assert "URL scheme must be http, https, ws, or wss" in str(exc_info.value)


def test_mcp_stdio_server_config_basic():
    """Test basic MCPStdioServerConfig."""
    config = MCPStdioServerConfig(name="test-server", command="python")
    assert config.name == "test-server"
    assert config.command == "python"
    assert config.args == []
    assert config.env == {}


def test_mcp_stdio_server_config_with_args_and_env():
    """Test MCPStdioServerConfig with args and env."""
    config = MCPStdioServerConfig(
        name="test-server",
        command="python",
        args=["-m", "server"],
        env={"DEBUG": "true", "PORT": "8080"},
    )
    assert config.name == "test-server"
    assert config.command == "python"
    assert config.args == ["-m", "server"]
    assert config.env == {"DEBUG": "true", "PORT": "8080"}


def test_mcp_stdio_server_config_invalid_name():
    """Test MCPStdioServerConfig with invalid server name."""
    with pytest.raises(ValidationError) as exc_info:
        MCPStdioServerConfig(name="", command="python")
    assert "Server name cannot be empty" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        MCPStdioServerConfig(name="invalid name with spaces", command="python")
    assert (
        "Server name can only contain letters, numbers, hyphens, and underscores"
        in str(exc_info.value)
    )


def test_mcp_stdio_server_config_invalid_command():
    """Test MCPStdioServerConfig with invalid command."""
    with pytest.raises(ValidationError) as exc_info:
        MCPStdioServerConfig(name="test-server", command="")
    assert "Command cannot be empty" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        MCPStdioServerConfig(name="test-server", command="python -m server")
    assert "Command should be a single executable without spaces" in str(exc_info.value)


def test_mcp_stdio_server_config_args_parsing():
    """Test MCPStdioServerConfig args parsing from string."""
    # Test basic space-separated parsing
    config = MCPStdioServerConfig(
        name="test-server",
        command="python",
        args="arg1 arg2 arg3",  # type: ignore
    )
    assert config.args == ["arg1", "arg2", "arg3"]

    # Test single argument
    config = MCPStdioServerConfig(
        name="test-server",
        command="python",
        args="single-arg",  # type: ignore
    )
    assert config.args == ["single-arg"]

    # Test empty string
    config = MCPStdioServerConfig(
        name="test-server",
        command="python",
        args="",  # type: ignore
    )
    assert config.args == []

    # Test quoted arguments
    config = MCPStdioServerConfig(
        name="test-server",
        command="python",
        args='--config "path with spaces" --debug',  # type: ignore
    )
    assert config.args == ["--config", "path with spaces", "--debug"]


def test_mcp_stdio_server_config_args_parsing_invalid_quotes():
    """Test MCPStdioServerConfig args parsing with invalid quotes."""
    with pytest.raises(ValidationError) as exc_info:
        MCPStdioServerConfig(
            name="test-server",
            command="python",
            args='--config "unmatched quote',  # type: ignore
        )
    assert "Invalid argument format" in str(exc_info.value)


def test_mcp_stdio_server_config_env_parsing():
    """Test MCPStdioServerConfig env parsing from string."""
    # Test basic env parsing
    config = MCPStdioServerConfig(
        name="test-server",
        command="python",
        env="DEBUG=true,PORT=8080",  # type: ignore
    )
    assert config.env == {"DEBUG": "true", "PORT": "8080"}

    # Test empty string
    config = MCPStdioServerConfig(
        name="test-server",
        command="python",
        env="",  # type: ignore
    )
    assert config.env == {}

    # Test single env var
    config = MCPStdioServerConfig(
        name="test-server",
        command="python",
        env="DEBUG=true",  # type: ignore
    )
    assert config.env == {"DEBUG": "true"}


def test_mcp_stdio_server_config_env_parsing_invalid():
    """Test MCPStdioServerConfig env parsing with invalid format."""
    with pytest.raises(ValidationError) as exc_info:
        MCPStdioServerConfig(
            name="test-server",
            command="python",
            env="INVALID_FORMAT",  # type: ignore
        )
    assert "must be in KEY=VALUE format" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        MCPStdioServerConfig(
            name="test-server",
            command="python",
            env="=value",  # type: ignore
        )
    assert "Environment variable key cannot be empty" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        MCPStdioServerConfig(
            name="test-server",
            command="python",
            env="123INVALID=value",  # type: ignore
        )
    assert "Invalid environment variable name" in str(exc_info.value)


def test_mcp_stdio_server_config_equality():
    """Test MCPStdioServerConfig equality operator."""
    server1 = MCPStdioServerConfig(
        name="test-server",
        command="python",
        args=["--verbose", "--debug", "--port=8080"],
        env={"DEBUG": "true", "PORT": "8080"},
    )

    server2 = MCPStdioServerConfig(
        name="test-server",
        command="python",
        args=["--verbose", "--debug", "--port=8080"],  # Same order
        env={"PORT": "8080", "DEBUG": "true"},  # Different order
    )

    # Should be equal because env is compared as a set
    assert server1 == server2

    # Test different args order
    server3 = MCPStdioServerConfig(
        name="test-server",
        command="python",
        args=["--debug", "--port=8080", "--verbose"],  # Different order
        env={"DEBUG": "true", "PORT": "8080"},
    )

    # Should NOT be equal because args order matters
    assert server1 != server3

    # Test different type
    assert server1 != "not a server config"


def test_mcp_shttp_server_config_basic():
    """Test basic MCPSHTTPServerConfig."""
    config = MCPSHTTPServerConfig(url="http://server1:8080")
    assert config.url == "http://server1:8080"
    assert config.api_key is None


def test_mcp_shttp_server_config_with_api_key():
    """Test MCPSHTTPServerConfig with API key."""
    config = MCPSHTTPServerConfig(url="http://server1:8080", api_key="test-api-key")
    assert config.url == "http://server1:8080"
    assert config.api_key == "test-api-key"


def test_mcp_shttp_server_config_invalid_url():
    """Test MCPSHTTPServerConfig with invalid URL format."""
    with pytest.raises(ValidationError) as exc_info:
        MCPSHTTPServerConfig(url="not_a_url")
    assert "URL must include a scheme" in str(exc_info.value)


def test_mcp_config_empty():
    """Test empty MCPConfig."""
    config = MCPConfig()
    assert config.sse_servers == []
    assert config.stdio_servers == []
    assert config.shttp_servers == []


def test_mcp_config_with_sse_servers():
    """Test MCPConfig with SSE servers."""
    sse_servers = [
        MCPSSEServerConfig(url="http://server1:8080"),
        MCPSSEServerConfig(url="http://server2:8080", api_key="test-key"),
    ]
    config = MCPConfig(sse_servers=sse_servers)
    assert len(config.sse_servers) == 2
    assert config.sse_servers[0].url == "http://server1:8080"
    assert config.sse_servers[1].url == "http://server2:8080"
    assert config.sse_servers[1].api_key == "test-key"


def test_mcp_config_with_stdio_servers():
    """Test MCPConfig with stdio servers."""
    stdio_servers = [
        MCPStdioServerConfig(name="server1", command="python"),
        MCPStdioServerConfig(name="server2", command="node", args=["server.js"]),
    ]
    config = MCPConfig(stdio_servers=stdio_servers)
    assert len(config.stdio_servers) == 2
    assert config.stdio_servers[0].name == "server1"
    assert config.stdio_servers[1].name == "server2"
    assert config.stdio_servers[1].args == ["server.js"]


def test_mcp_config_with_shttp_servers():
    """Test MCPConfig with SHTTP servers."""
    shttp_servers = [
        MCPSHTTPServerConfig(url="http://server1:8080"),
        MCPSHTTPServerConfig(url="http://server2:8080", api_key="test-key"),
    ]
    config = MCPConfig(shttp_servers=shttp_servers)
    assert len(config.shttp_servers) == 2
    assert config.shttp_servers[0].url == "http://server1:8080"
    assert config.shttp_servers[1].url == "http://server2:8080"
    assert config.shttp_servers[1].api_key == "test-key"


def test_mcp_config_with_all_server_types():
    """Test MCPConfig with all server types."""
    sse_server = MCPSSEServerConfig(url="http://sse-server:8080")
    stdio_server = MCPStdioServerConfig(name="stdio-server", command="python")
    shttp_server = MCPSHTTPServerConfig(url="http://shttp-server:8080")

    config = MCPConfig(
        sse_servers=[sse_server],
        stdio_servers=[stdio_server],
        shttp_servers=[shttp_server],
    )

    assert len(config.sse_servers) == 1
    assert len(config.stdio_servers) == 1
    assert len(config.shttp_servers) == 1
    assert config.sse_servers[0].url == "http://sse-server:8080"
    assert config.stdio_servers[0].name == "stdio-server"
    assert config.shttp_servers[0].url == "http://shttp-server:8080"


def test_mcp_config_validate_servers():
    """Test MCPConfig server validation."""
    # Valid configuration should not raise
    config = MCPConfig(
        sse_servers=[
            MCPSSEServerConfig(url="http://server1:8080"),
            MCPSSEServerConfig(url="http://server2:8080"),
        ]
    )
    config.validate_servers()  # Should not raise

    # Duplicate URLs in sse_servers should raise
    config = MCPConfig(
        sse_servers=[
            MCPSSEServerConfig(url="http://server1:8080"),
            MCPSSEServerConfig(url="http://server1:8080"),
        ]
    )
    with pytest.raises(ValueError) as exc_info:
        config.validate_servers()
    assert "Duplicate MCP server URLs are not allowed" in str(exc_info.value)


def test_mcp_config_validate_servers_shttp_duplicates():
    """Test MCPConfig validation for duplicate URLs in shttp_servers."""
    # Note: Current implementation only validates sse_servers,
    # but this test documents expected behavior for shttp_servers
    config = MCPConfig(
        shttp_servers=[
            MCPSHTTPServerConfig(url="http://server1:8080"),
            MCPSHTTPServerConfig(url="http://server1:8080"),
        ]
    )
    # This currently passes but should ideally fail - testing current behavior
    config.validate_servers()  # Currently doesn't validate shttp_servers


def test_mcp_config_validate_servers_stdio_duplicates():
    """Test MCPConfig validation for duplicate names in stdio_servers."""
    # Note: Current implementation doesn't validate stdio server names,
    # but this test documents expected behavior
    config = MCPConfig(
        stdio_servers=[
            MCPStdioServerConfig(name="server1", command="python"),
            MCPStdioServerConfig(name="server1", command="node"),
        ]
    )
    # This currently passes but should ideally fail - testing current behavior
    config.validate_servers()  # Currently doesn't validate stdio server names


def test_mcp_config_validate_servers_cross_type_duplicates():
    """Test MCPConfig validation for duplicate URLs between sse and shttp servers."""
    # Note: Current implementation doesn't check cross-type duplicates,
    # but this test documents expected behavior
    config = MCPConfig(
        sse_servers=[MCPSSEServerConfig(url="http://server1:8080")],
        shttp_servers=[MCPSHTTPServerConfig(url="http://server1:8080")],
    )
    # This currently passes but should ideally fail - testing current behavior
    config.validate_servers()  # Currently doesn't check cross-type duplicates


def test_mcp_config_from_toml_section_basic():
    """Test MCPConfig.from_toml_section with basic data."""
    data = {
        "sse_servers": ["http://server1:8080"],
    }
    result = MCPConfig.from_toml_section(data)
    assert "mcp" in result
    assert len(result["mcp"].sse_servers) == 1
    assert result["mcp"].sse_servers[0].url == "http://server1:8080"


def test_mcp_config_from_toml_section_with_stdio():
    """Test MCPConfig.from_toml_section with stdio servers."""
    data = {
        "sse_servers": ["http://server1:8080"],
        "stdio_servers": [
            {
                "name": "test-server",
                "command": "python",
                "args": ["-m", "server"],
                "env": {"DEBUG": "true"},
            }
        ],
    }
    result = MCPConfig.from_toml_section(data)
    assert "mcp" in result
    assert len(result["mcp"].sse_servers) == 1
    assert len(result["mcp"].stdio_servers) == 1
    assert result["mcp"].stdio_servers[0].name == "test-server"
    assert result["mcp"].stdio_servers[0].command == "python"
    assert result["mcp"].stdio_servers[0].args == ["-m", "server"]
    assert result["mcp"].stdio_servers[0].env == {"DEBUG": "true"}


def test_mcp_config_from_toml_section_with_shttp():
    """Test MCPConfig.from_toml_section with SHTTP servers."""
    data = {
        "shttp_servers": [{"url": "http://server1:8080", "api_key": "test-key"}],
    }
    result = MCPConfig.from_toml_section(data)
    assert "mcp" in result
    assert len(result["mcp"].shttp_servers) == 1
    assert result["mcp"].shttp_servers[0].url == "http://server1:8080"
    assert result["mcp"].shttp_servers[0].api_key == "test-key"


def test_mcp_config_from_toml_section_invalid():
    """Test MCPConfig.from_toml_section with invalid data."""
    data = {
        "sse_servers": ["not_a_url"],
    }
    with pytest.raises(ValueError) as exc_info:
        MCPConfig.from_toml_section(data)
    assert "URL must include a scheme" in str(exc_info.value)


def test_mcp_config_merge():
    """Test MCPConfig merge functionality."""
    config1 = MCPConfig(
        sse_servers=[MCPSSEServerConfig(url="http://server1:8080")],
        stdio_servers=[MCPStdioServerConfig(name="server1", command="python")],
        shttp_servers=[MCPSHTTPServerConfig(url="http://shttp1:8080")],
    )

    config2 = MCPConfig(
        sse_servers=[MCPSSEServerConfig(url="http://server2:8080")],
        stdio_servers=[MCPStdioServerConfig(name="server2", command="node")],
        shttp_servers=[MCPSHTTPServerConfig(url="http://shttp2:8080")],
    )

    merged = config1.merge(config2)

    assert len(merged.sse_servers) == 2
    assert len(merged.stdio_servers) == 2
    assert len(merged.shttp_servers) == 2
    assert merged.sse_servers[0].url == "http://server1:8080"
    assert merged.sse_servers[1].url == "http://server2:8080"
    assert merged.stdio_servers[0].name == "server1"
    assert merged.stdio_servers[1].name == "server2"
    assert merged.shttp_servers[0].url == "http://shttp1:8080"
    assert merged.shttp_servers[1].url == "http://shttp2:8080"


def test_mcp_config_extra_fields_forbidden():
    """Test that extra fields are forbidden in MCPConfig."""
    with pytest.raises(ValidationError) as exc_info:
        MCPConfig(extra_field="value")  # type: ignore
    assert "Extra inputs are not permitted" in str(exc_info.value)


def test_mcp_config_complex_urls():
    """Test MCPConfig with complex URLs."""
    config = MCPConfig(
        sse_servers=[
            MCPSSEServerConfig(url="https://user:pass@server1:8080/path?query=1"),
            MCPSSEServerConfig(url="wss://server2:8443/ws"),
            MCPSSEServerConfig(url="http://subdomain.example.com:9090"),
        ]
    )
    config.validate_servers()  # Should not raise any exception
    assert len(config.sse_servers) == 3
