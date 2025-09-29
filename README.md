# OpenHands Agent SDK

A clean, modular SDK for building AI agents with OpenHands. This project represents a complete architectural refactor from OpenHands V0, emphasizing simplicity, maintainability, and developer experience.

## Project Overview

The OpenHands Agent SDK provides a streamlined framework for creating AI agents that can interact with tools, manage conversations, and integrate with various LLM providers.

## Packages

This repository contains three main packages:

- **`openhands-sdk`**: Core SDK functionality including agents, conversations, LLM integration, and tool system
- **`openhands-tools`**: Runtime tool implementations (BashTool, FileEditorTool, TaskTrackerTool, BrowserToolSet)
- **`openhands-agent-server`**: REST API and WebSocket server for remote agent interactions

## Repository Structure

```plain
agent-sdk/
├── Makefile                            # Build and development commands
├── pyproject.toml                      # Workspace configuration
├── uv.lock                             # Dependency lock file
├── examples/                           # Usage examples
│   ├── 01_hello_world.py               # Basic agent setup (default tools preset)
│   ├── 02_custom_tools.py              # Custom tool implementation with explicit executor
│   ├── 03_activate_microagent.py       # Microagent usage
│   ├── 04_confirmation_mode_example.py # Interactive confirmation mode
│   ├── 05_use_llm_registry.py          # LLM registry usage
│   ├── 06_interactive_terminal_w_reasoning.py # Terminal interaction with reasoning models
│   ├── 07_mcp_integration.py           # MCP integration
│   ├── 08_mcp_with_oauth.py            # MCP integration with OAuth
│   ├── 09_pause_example.py             # Pause and resume agent execution
│   ├── 10_persistence.py               # Conversation persistence
│   ├── 11_async.py                     # Async agent usage
│   ├── 12_custom_secrets.py            # Custom secrets management
│   ├── 13_get_llm_metrics.py           # LLM metrics and monitoring
│   ├── 14_context_condenser.py         # Context condensation
│   ├── 15_browser_use.py               # Browser automation tools
│   ├── 16_llm_security_analyzer.py     # LLM security analysis
│   └── 17_image_input.py               # Image input and vision support
├── openhands/              # Main SDK packages
│   ├── agent_server/       # REST API and WebSocket server
│   │   ├── api.py          # FastAPI application
│   │   ├── config.py       # Server configuration
│   │   ├── models.py       # API models
│   │   └── pyproject.toml  # Agent server package configuration
│   ├── sdk/                # Core SDK functionality
│   │   ├── agent/          # Agent implementations
│   │   ├── context/        # Context management system
│   │   ├── conversation/   # Conversation management
│   │   ├── event/          # Event system
│   │   ├── io/             # I/O abstractions
│   │   ├── llm/            # LLM integration layer
│   │   ├── mcp/            # Model Context Protocol integration
│   │   ├── preset/         # Default agent presets
│   │   ├── security/       # Security analysis tools
│   │   ├── tool/           # Tool system
│   │   ├── utils/          # Core utilities
│   │   ├── logger.py       # Logging configuration
│   │   └── pyproject.toml  # SDK package configuration
│   └── tools/              # Runtime tool implementations
│       ├── execute_bash/   # Bash execution tool
│       ├── str_replace_editor/  # File editing tool
│       ├── task_tracker/   # Task tracking tool
│       ├── browser_use/    # Browser automation tools
│       ├── utils/          # Tool utilities
│       └── pyproject.toml  # Tools package configuration
├── scripts/                # Utility scripts
│   └── conversation_viewer.py # Conversation visualization tool
└── tests/                  # Test suites
    ├── agent_server/       # Agent server tests
    ├── cross/              # Cross-package tests
    ├── fixtures/           # Test fixtures and data
    ├── integration/        # Integration tests
    ├── sdk/                # SDK unit tests
    └── tools/              # Tools unit tests
```

## Installation & Quickstart

### Prerequisites

- Python 3.12+
- `uv` package manager (version 0.8.13+)

### Setup

```bash
# Clone the repository
git clone https://github.com/All-Hands-AI/agent-sdk.git
cd agent-sdk

# Install dependencies and setup development environment
make build

# Verify installation
uv run python examples/01_hello_world.py
```

### Hello World Example

```python
import os
from pydantic import SecretStr
from openhands.sdk import LLM, Conversation
from openhands.sdk.preset.default import get_default_agent

# Configure LLM
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."
llm = LLM(
    model="litellm_proxy/anthropic/claude-sonnet-4-5-20250929",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

# Create agent with default tools and configuration
cwd = os.getcwd()
agent = get_default_agent(
    llm=llm,
    working_dir=cwd,
    cli_mode=True,  # Disable browser tools for CLI environments
)

# Create conversation and interact with agent
conversation = Conversation(agent=agent)

# Send message and run
conversation.send_message("Create a Python file that prints 'Hello, World!'")
conversation.run()
```

## Core Concepts

### Agents

Agents are the central orchestrators that coordinate between LLMs and tools. The SDK provides two main approaches for creating agents:

#### Using Default Presets (Recommended)

```python
from openhands.sdk.preset.default import get_default_agent

# Get a fully configured agent with default tools and settings
agent = get_default_agent(
    llm=llm,
    working_dir=os.getcwd(),
    cli_mode=True,  # Disable browser tools for CLI environments
)
```

#### Manual Agent Configuration

```python
from openhands.sdk import Agent
from openhands.sdk.tool import ToolSpec, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool

# Register tools
register_tool("BashTool", BashTool)
register_tool("FileEditorTool", FileEditorTool)
register_tool("TaskTrackerTool", TaskTrackerTool)

# Create agent with explicit tool specifications
agent = Agent(
    llm=llm,
    tools=[
        ToolSpec(name="BashTool", params={"working_dir": os.getcwd()}),
        ToolSpec(name="FileEditorTool"),
        ToolSpec(name="TaskTrackerTool", params={"save_dir": os.getcwd()}),
    ],
)
```

### LLM Integration

The SDK supports multiple LLM providers through a unified interface:

```python
from openhands.sdk import LLM, LLMRegistry
from pydantic import SecretStr

# Direct LLM configuration
llm = LLM(
    model="gpt-4",
    api_key=SecretStr("your-api-key"),
    base_url="https://api.openai.com/v1"
)

# Using LLM registry for shared configurations
registry = LLMRegistry()
registry.add("default", llm)
llm = registry.get("default")
```

### Tools

Tools provide agents with capabilities to interact with the environment. The SDK includes several built-in tools:

- **BashTool**: Execute bash commands in a persistent shell session
- **FileEditorTool**: Create, edit, and manage files with advanced editing capabilities  
- **TaskTrackerTool**: Organize and track development tasks systematically
- **BrowserToolSet**: Automate web browser interactions (disabled in CLI mode)

#### Using Default Preset (Recommended)

The easiest way to get started is using the default agent preset, which includes all tools:

```python
from openhands.sdk.preset.default import get_default_agent

agent = get_default_agent(
    llm=llm,
    working_dir=os.getcwd(),
    cli_mode=True,  # Disable browser tools for CLI environments
)
```

#### Manual Tool Configuration

For more control, you can configure tools explicitly:

```python
from openhands.sdk.tool import ToolSpec, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool

# Register tools
register_tool("BashTool", BashTool)
register_tool("FileEditorTool", FileEditorTool)
register_tool("TaskTrackerTool", TaskTrackerTool)

# Create tool specifications
tools = [
    ToolSpec(name="BashTool", params={"working_dir": os.getcwd()}),
    ToolSpec(name="FileEditorTool"),
    ToolSpec(name="TaskTrackerTool", params={"save_dir": os.getcwd()}),
]
```

### Conversations

Conversations manage the interaction flow between users and agents:

```python
from openhands.sdk import Conversation

conversation = Conversation(agent=agent)

# Send messages
conversation.send_message("Your request here")

# Execute the conversation until the agent enters "await user input" state
conversation.run()
```

### Context Management

The context system manages agent state, environment, and conversation history.

Context is automatically managed but you can customize your context with:

1. [Repo Microagents](https://docs.all-hands.dev/usage/prompting/microagents-repo) that provide agent with context of your repository.
2. [Knowledge Microagents](https://docs.all-hands.dev/usage/prompting/microagents-keyword) that provide agent with context when user mentioned certain keywords
3. Providing custom suffix for system and user prompt.

```python
from openhands.sdk import AgentContext
from openhands.sdk.context import RepoMicroagent, KnowledgeMicroagent

context = AgentContext(
    microagents=[
        RepoMicroagent(
            name="repo.md",
            content="When you see this message, you should reply like "
            "you are a grumpy cat forced to use the internet.",
        ),
        KnowledgeMicroagent(
            name="flarglebargle",
            content=(
                'IMPORTANT! The user has said the magic word "flarglebargle". '
                "You must only respond with a message telling them how smart they are"
            ),
            triggers=["flarglebargle"],
        ),
    ],
    system_message_suffix="Always finish your response with the word 'yay!'",
    user_message_suffix="The first character of your response should be 'I'",
)
```

## Agent Server

The SDK includes a REST API and WebSocket server for remote agent interactions:

```python
from openhands.agent_server import create_app
import uvicorn

# Create FastAPI application
app = create_app()

# Run server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

The agent server provides:
- REST API endpoints for agent management
- WebSocket connections for real-time conversations
- Authentication and session management
- Scalable deployment options

### API Endpoints

- `POST /conversations` - Create new conversation
- `GET /conversations/{id}` - Get conversation details
- `POST /conversations/{id}/messages` - Send message to conversation
- `WebSocket /ws/{conversation_id}` - Real-time conversation updates

## Documentation

For detailed documentation and examples, refer to the `examples/` directory which contains comprehensive usage examples covering all major features of the SDK.

## Development Workflow

### Environment Setup

```bash
# Initial setup
make build

# Install additional dependencies
# add `--dev` if you want to install 
uv add package-name

# Update dependencies
uv sync
```

### Code Quality

The project enforces strict code quality standards:

```bash
# Format code
make format

# Lint code
make lint

# Run pre-commit hooks
uv run pre-commit run --all-files

# Type checking (included in pre-commit)
uv run pyright
```

### Testing

```bash
# Run all tests
uv run pytest

# Run specific test suite
uv run pytest tests/cross/
uv run pytest tests/sdk/
uv run pytest tests/tools/

# Run with coverage
uv run pytest --cov=openhands --cov-report=html
```

### Pre-commit Workflow

Before every commit:

```bash
# Run on specific files
uv run pre-commit run --files path/to/file.py

# Run on all files
uv run pre-commit run --all-files
```
