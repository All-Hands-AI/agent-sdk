# MCP (Model Context Protocol) Integration

The OpenHands Agent SDK provides seamless integration with the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), enabling agents to connect to external tools and services through a standardized protocol.

## Quick Start

```python
import os
from pydantic import SecretStr
from openhands.sdk import LLM, Agent, Conversation, Message, TextContent, create_mcp_tools
from openhands.tools import BashTool, FileEditorTool

# Configure LLM
llm = LLM(
    model="anthropic/claude-sonnet-4-20250514",
    api_key=SecretStr(os.getenv("ANTHROPIC_API_KEY")),
)

# Setup standard tools
tools = [
    BashTool(working_dir=os.getcwd()),
    FileEditorTool(),
]

# Add MCP tools
mcp_config = {
    "mcpServers": {
        "fetch": {
            "command": "uvx",
            "args": ["mcp-server-fetch"]
        }
    }
}

mcp_tools = create_mcp_tools(mcp_config, timeout=30)
tools.extend(mcp_tools)

# Create agent with combined tools
agent = Agent(llm=llm, tools=tools)
conversation = Conversation(agent=agent)

# Use MCP-enabled agent
conversation.send_message(
    Message(
        role="user",
        content=[TextContent(text="Fetch the latest news from https://example.com")]
    )
)
conversation.run()
```

## Configuration Format

OpenHands Agent SDK uses the [FastMCP configuration format](https://gofastmcp.com/clients/client#configuration-format), which provides a standardized way to configure MCP servers.

```python
config = {
    "mcpServers": {
        "server_name": {
            # Remote HTTP/SSE server
            "transport": "http",  # or "sse" 
            "url": "https://api.example.com/mcp",
            "headers": {"Authorization": "Bearer token"},
            "auth": "oauth"  # or bearer token string
        },
        "local_server": {
            # Local stdio server
            "transport": "stdio",
            "command": "python",
            "args": ["./server.py", "--verbose"],
            "env": {"DEBUG": "true"},
            "cwd": "/path/to/server",
        }
    }
}
```
