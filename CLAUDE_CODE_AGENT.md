# Claude Code Agent

The `ClaudeCodeAgent` is an alternate agent implementation that uses the [Claude Code SDK](https://github.com/anthropics/claude-code-sdk-python) under the hood while maintaining the same API/interface as the standard OpenHands `Agent`.

## Features

- **Same API**: Drop-in replacement for the standard `Agent` class
- **Claude Code Integration**: Leverages Claude Code's advanced reasoning and tool execution capabilities
- **Tool Compatibility**: Automatically converts OpenHands tools to Claude Code MCP (Model Context Protocol) tools
- **Enhanced Capabilities**: Benefits from Claude Code's built-in tools and execution environment
- **Async Support**: Handles Claude Code's async nature transparently

## Installation

```bash
pip install claude-code-sdk
npm install -g @anthropic-ai/claude-code
```

## Usage

### Basic Usage

```python
from openhands.sdk.agent import ClaudeCodeAgent
from openhands.sdk.conversation import Conversation
from openhands.sdk.llm import LLM, Message, TextContent
from openhands.tools import BashTool, FileEditorTool
from pydantic import SecretStr

# Create LLM instance
llm = LLM(
    model="claude-3-5-sonnet-20241022",
    api_key=SecretStr("your-api-key")
)

# Create tools
tools = [
    BashTool.create(working_dir="/tmp"),
    FileEditorTool.create(),
]

# Create Claude Code agent
agent = ClaudeCodeAgent(llm=llm, tools=tools)

# Use with Conversation (same as regular Agent)
conversation = Conversation(agent=agent)
```

### With Custom Claude Code Options

```python
# Configure Claude Code specific options
claude_options = {
    "allowed_tools": ["Read", "Write", "Bash"],  # Claude Code built-in tools
    "permission_mode": "acceptEdits",  # Auto-accept file edits
    "max_turns": 10,
    "system_prompt": "You are a helpful coding assistant.",
}

agent = ClaudeCodeAgent(
    llm=llm,
    tools=tools,
    claude_options=claude_options
)
```

## How It Works

### Tool Conversion

The `ClaudeCodeAgent` automatically converts OpenHands tools to Claude Code MCP tools:

1. **OpenHands Tool** → **MCP Tool Function**: Each OpenHands tool is wrapped in an async function
2. **Parameter Mapping**: Tool parameters are converted from JSON schema to Python types
3. **Execution Bridge**: Tool execution results are converted back to Claude Code format
4. **Error Handling**: Exceptions are caught and converted to appropriate error responses

### Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   OpenHands     │    │  ClaudeCodeAgent │    │   Claude Code   │
│   Conversation  │───▶│                  │───▶│   SDK Client    │
│                 │    │  - Tool Convert  │    │                 │
│                 │    │  - Async Bridge  │    │  - MCP Tools    │
│                 │    │  - Event Mapping │    │  - Execution    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Event Flow

1. **User Message** → Sent to Claude Code SDK
2. **Claude Response** → Processed and converted to OpenHands events
3. **Tool Calls** → Executed through OpenHands tool executors
4. **Results** → Converted back to Claude Code format

## API Compatibility

The `ClaudeCodeAgent` maintains full API compatibility with the standard `Agent`:

| Method/Property | Standard Agent | ClaudeCodeAgent | Notes |
|----------------|----------------|-----------------|-------|
| `__init__()` | ✅ | ✅ | Additional `claude_options` parameter |
| `init_state()` | ✅ | ✅ | Same interface |
| `step()` | ✅ | ✅ | Same interface, async execution under the hood |
| `system_message` | ✅ | ✅ | Same property |
| `tools` | ✅ | ✅ | Same tool format |
| `name` | ✅ | ✅ | Returns "ClaudeCodeAgent" |

## Configuration Options

The `claude_options` parameter accepts a dictionary with Claude Code SDK options:

```python
claude_options = {
    # Tool configuration
    "allowed_tools": ["Read", "Write", "Bash"],
    "disallowed_tools": ["SomeRestrictedTool"],
    
    # Execution settings
    "permission_mode": "acceptEdits",  # "default", "acceptEdits", "plan", "bypassPermissions"
    "max_turns": 10,
    "continue_conversation": False,
    
    # System prompts
    "system_prompt": "Custom system prompt",
    "append_system_prompt": "Additional instructions",
    
    # Working directory
    "cwd": "/path/to/working/directory",
    
    # Environment variables
    "env": {"CUSTOM_VAR": "value"},
    
    # Model selection
    "model": "claude-3-5-sonnet-20241022",
}
```

## Testing

The implementation includes comprehensive tests:

- **Unit Tests**: `tests/sdk/agent/test_claude_code_agent.py`
- **Integration Tests**: `tests/integration/test_claude_code_agent_integration.py`

Run tests with:
```bash
uv run pytest tests/sdk/agent/test_claude_code_agent.py -v
uv run pytest tests/integration/test_claude_code_agent_integration.py -v
```

## Examples

See `examples/18_claude_code_agent.py` for a complete working example.

## Limitations

1. **Dependency**: Requires `claude-code-sdk` and Claude Code CLI to be installed
2. **Async Nature**: Some operations may have different timing characteristics
3. **Tool Compatibility**: Not all OpenHands tools may work perfectly with Claude Code's execution model
4. **API Key**: Requires Anthropic API key for Claude models

## Error Handling

The agent handles various error scenarios gracefully:

- **Missing Dependencies**: Graceful fallback when Claude Code SDK is not available
- **Tool Execution Errors**: Proper error reporting through OpenHands event system
- **Claude Code Errors**: Conversion of Claude Code exceptions to OpenHands error events
- **Network Issues**: Timeout and retry handling through underlying SDK

## Contributing

When contributing to the Claude Code agent:

1. Ensure all tests pass
2. Add tests for new functionality
3. Maintain API compatibility with the standard Agent
4. Update documentation for new features
5. Handle the conditional import pattern properly