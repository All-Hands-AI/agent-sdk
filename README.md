# OpenHands Agent SDK

A clean, modular SDK for building AI agents with OpenHands. This project represents a complete architectural refactor from OpenHands V0, emphasizing simplicity, maintainability, and developer experience.

## Project Overview

The OpenHands Agent SDK provides a streamlined framework for creating AI agents that can interact with tools, manage conversations, and integrate with various LLM providers.

## Repository Structure

```plain
agent-sdk/
├── Makefile                            # Build and development commands
├── pyproject.toml                      # Workspace configuration
├── uv.lock                             # Dependency lock file
├── examples/                           # Usage examples
│   ├── 01_hello_world.py               # Basic agent setup
│   ├── 02_custom_tools.py              # Custom tool implementation
│   ├── 03_activate_microagent.py       # Microagent usage
│   ├── 04_confirmation_mode_example.py # Interactive mode
│   ├── 05_use_llm_registry.py          # LLM registry usage
│   ├── 06_interactive_terminal_w_reasoning.py # Terminal interaction with reasoning
│   ├── 07_mcp_integration.py           # MCP integration
│   ├── 08_mcp_with_oauth.py            # MCP integration with OAuth
│   ├── 09_pause_example.py             # Pause and resume agent execution
│   ├── 10_persistence.py               # Conversation persistence
│   └── 11_async.py                     # Async agent usage
├── openhands/              # Main SDK packages
│   ├── sdk/                # Core SDK functionality
│   │   ├── agent/          # Agent implementations
│   │   ├── context/        # Context management system
│   │   ├── conversation/   # Conversation management
│   │   ├── event/          # Event system
│   │   ├── io/             # I/O abstractions
│   │   ├── llm/            # LLM integration layer
│   │   ├── mcp/            # Model Context Protocol integration
│   │   ├── tool/           # Tool system
│   │   ├── utils/          # Core utilities
│   │   ├── logger.py       # Logging configuration
│   │   └── pyproject.toml  # SDK package configuration
│   └── tools/              # Runtime tool implementations
│       ├── execute_bash/   # Bash execution tool
│       ├── str_replace_editor/  # File editing tool
│       ├── task_tracker/   # Task tracking tool
│       ├── utils/          # Tool utilities
│       └── pyproject.toml  # Tools package configuration
└── tests/                  # Test suites
    ├── cross/              # Cross-package tests
    ├── fixtures/           # Test fixtures and data
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
from openhands.sdk import LLM, Agent, Conversation, Message, TextContent
from openhands.tools import BashTool, FileEditorTool, TaskTrackerTool

# Configure LLM
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."
llm = LLM(
    model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

# Setup tools
cwd = os.getcwd()
tools = [
    BashTool.create(working_dir=cwd),
    FileEditorTool.create(),
]

# Create agent and conversation
agent = Agent(llm=llm, tools=tools)
conversation = Conversation(agent=agent)

# Send message and run
conversation.send_message(
    Message(
        role="user",
        content=[TextContent(text="Create a Python file that prints 'Hello, World!'")]
    )
)
conversation.run()
```

## Core Concepts

### Agents

Agents are the central orchestrators that coordinate between LLMs and tools:

```python
from openhands.sdk import Agent, LLM
from openhands.tools import BashTool, FileEditorTool

agent = Agent(
    llm=llm,
    tools=[BashTool.create(), FileEditorTool.create()],
    # Optional: custom context, microagents, etc.
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
llm = registry.get_llm("default")
```

### Tools

Tools provide agents with capabilities to interact with the environment:

#### Simplified Pattern (Recommended)

```python
from openhands.sdk import TextContent, ImageContent
from openhands.tools import BashTool, FileEditorTool, TaskTrackerTool

# Direct instantiation with simplified API
tools = [
    BashTool.create(working_dir=os.getcwd()),
    FileEditorTool.create(),
    TaskTrackerTool.create(save_dir=os.getcwd()),
]
```

#### Advanced Pattern (For explicitly maintained tool executor)

We explicitly define a `BashExecutor` in this example:

```python
from openhands.tools import BashExecutor, execute_bash_tool

# Explicit executor creation for reuse or customization
bash_executor = BashExecutor(working_dir=os.getcwd())
bash_tool = execute_bash_tool.set_executor(executor=bash_executor)
```

And we can later re-use this bash terminal instance to define a custom tool:

```python
from collections.abc import Sequence
from openhands.sdk.tool import ActionBase, ObservationBase, ToolExecutor

class GrepAction(ActionBase):
    pattern: str = Field(description="Regex to search for")
    path: str = Field(
        default=".", description="Directory to search (absolute or relative)"
    )
    include: str | None = Field(
        default=None, description="Optional glob to filter files (e.g. '*.py')"
    )


class GrepObservation(ObservationBase):
    output: str = Field(default='')

    @property
    def agent_observation(self) -> Sequence[TextContent | ImageContent]:
        return [TextContent(text=self.output)]

# --- Executor ---
class GrepExecutor(ToolExecutor[GrepAction, GrepObservation]):
    def __init__(self, bash: BashExecutor):
        self.bash = bash

    def __call__(self, action: GrepAction) -> GrepObservation:
        root = os.path.abspath(action.path)
        pat = shlex.quote(action.pattern)
        root_q = shlex.quote(root)

        # Use grep -r; add --include when provided
        if action.include:
            inc = shlex.quote(action.include)
            cmd = f"grep -rHnE --include {inc} {pat} {root_q} 2>/dev/null | head -100"
        else:
            cmd = f"grep -rHnE {pat} {root_q} 2>/dev/null | head -100"

        result = self.bash(ExecuteBashAction(command=cmd, security_risk="LOW"))
        return GrepObservation(output=result.output.strip() or '')
```

### Conversations

Conversations manage the interaction flow between users and agents:

```python
from openhands.sdk import Conversation, Message, TextContent

conversation = Conversation(agent=agent)

# Send messages
conversation.send_message(
    Message(role="user", content=[TextContent(text="Your request here")])
)

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

## Spec System

The OpenHands Agent SDK includes a powerful specification system that allows you to define and instantiate agents, tools, and condensers using declarative configuration. This system provides a clean, serializable way to configure complex agent setups.

### Agent Specifications

Define complete agent configurations using `AgentSpec`:

```python
from openhands.sdk.agent import AgentSpec
from openhands.sdk.tool import ToolSpec
from openhands.sdk.context.condenser import LLMSummarizingCondenser

# Define an agent specification
agent_spec = AgentSpec(
    llm={
        "model": "gpt-4",
        "api_key": "your-api-key",
        "base_url": "https://api.openai.com/v1"
    },
    tools=[
        ToolSpec(name="BashTool", params={"working_dir": "/workspace"}),
        ToolSpec(name="FileEditorTool"),
    ],
    condenser=LLMSummarizingCondenser(
        llm={"model": "gpt-4", "api_key": "your-api-key"},
        max_size=80,
        keep_first=10
    ),
    agent_context={
        "system_message_suffix": "Always be helpful and concise."
    }
)

# Create agent from specification
agent = AgentBase.from_spec(agent_spec)
```

### Tool Specifications

Configure tools with `ToolSpec`:

```python
from openhands.sdk.tool import ToolSpec

# Simple tool specification
bash_spec = ToolSpec(name="BashTool", params={"working_dir": "/app"})

# Tool with complex parameters
editor_spec = ToolSpec(
    name="FileEditorTool",
    params={
        "max_file_size": 1000000,
        "allowed_extensions": [".py", ".js", ".md"]
    }
)
```

### Benefits of the Spec System

1. **Serializable Configuration**: Specs can be easily serialized to/from JSON, YAML, or other formats
2. **Validation**: Built-in validation ensures configurations are correct before instantiation
3. **Reusability**: Share and reuse agent configurations across different environments
4. **Version Control**: Track agent configurations alongside your code
5. **Dynamic Loading**: Load agent configurations from external sources at runtime

### Example: Configuration File

```python
import json
from openhands.sdk.agent import AgentSpec, AgentBase

# Save configuration to file
config = {
    "llm": {"model": "gpt-4", "api_key": "your-key"},
    "tools": [
        {"name": "BashTool", "params": {"working_dir": "/workspace"}},
        {"name": "FileEditorTool"}
    ]
}

with open("agent_config.json", "w") as f:
    json.dump(config, f)

# Load and create agent from file
with open("agent_config.json", "r") as f:
    config = json.load(f)

agent_spec = AgentSpec(**config)
agent = AgentBase.from_spec(agent_spec)
```

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
