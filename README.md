# OpenHands Agent SDK

A clean, modular SDK for building AI agents with OpenHands. This project represents a complete architectural refactor from OpenHands V0, emphasizing simplicity, maintainability, and developer experience.

## Project Overview

The OpenHands Agent SDK provides a streamlined framework for creating AI agents that can interact with tools, manage conversations, and integrate with various LLM providers.
## Repository Structure

```
agent-sdk/
├── Makefile                # Build and development commands
├── pyproject.toml          # Workspace configuration
├── uv.lock                 # Dependency lock file
├── examples/               # Usage examples
│   ├── 1_hello_world.py    # Basic agent setup
│   ├── 2_custom_tools.py   # Custom tool implementation
│   ├── 3_activate_microagent.py  # Microagent usage
│   ├── 4_confirmation_mode_example.py  # Interactive mode
│   ├── 5_use_llm_registry.py  # LLM registry usage
│   └── 6_interactive_terminal.py  # Terminal interaction
├── openhands/              # Main SDK packages
│   ├── sdk/                # Core SDK functionality
│   │   ├── agent/          # Agent implementations
│   │   ├── config/         # Configuration management
│   │   ├── context/        # Context management system
│   │   ├── conversation/   # Conversation management
│   │   ├── event/          # Event system
│   │   ├── llm/            # LLM integration layer
│   │   ├── tool/           # Tool system
│   │   ├── utils/          # Core utilities
│   │   ├── logger.py       # Logging configuration
│   │   └── pyproject.toml  # SDK package configuration
│   └── tools/              # Runtime tool implementations
│       ├── execute_bash/   # Bash execution tool
│       ├── str_replace_editor/  # File editing tool
│       ├── utils/          # Tool utilities
│       └── pyproject.toml  # Tools package configuration
└── tests/                  # Test suites
    ├── integration/        # Cross-package integration tests
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
uv run python examples/1_hello_world.py
```

### Hello World Example

```python
import os
from pydantic import SecretStr
from openhands.sdk import LLM, Agent, Conversation, Message, TextContent
from openhands.tools import BashTool, FileEditorTool

# Configure LLM
llm = LLM(
    model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(os.getenv("LITELLM_API_KEY")),
)

# Setup tools
tools = [
    BashTool(working_dir=os.getcwd()),
    FileEditorTool(),
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

Agents are the central orchestrators that coordinate between LLMs, tools, and conversations:

```python
from openhands.sdk import Agent, LLM
from openhands.tools import BashTool, FileEditorTool

agent = Agent(
    llm=llm,
    tools=[BashTool(), FileEditorTool()],
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
from openhands.tools import BashTool, FileEditorTool

# Direct instantiation with simplified API
tools = [
    BashTool(working_dir=os.getcwd()),
    FileEditorTool(),
]
```

#### Advanced Pattern (For Custom Tools)
```python
from openhands.tools import BashExecutor, execute_bash_tool

# Explicit executor creation for reuse or customization
bash_executor = BashExecutor(working_dir=os.getcwd())
bash_tool = execute_bash_tool.set_executor(executor=bash_executor)
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

# Execute the conversation
conversation.run()
```

### Context Management

The context system manages agent state, environment, and conversation history:

```python
from openhands.sdk import AgentContext

# Context is automatically managed but can be customized
context = AgentContext(
    # Custom environment variables, working directory, etc.
)
```

## Development Workflow

### Environment Setup

```bash
# Initial setup
make build

# Install additional dependencies
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

# Type checking (automatic via pre-commit)
uv run pyright
```

### Testing

```bash
# Run all tests
uv run pytest

# Run specific test suite
uv run pytest tests/sdk/
uv run pytest tests/tools/
uv run pytest tests/integration/

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

## Contributing

### Adding New Tools

1. Create a new directory under `openhands/tools/`
2. Implement the tool following the existing patterns:

```python
from openhands.sdk.tool import Tool, ActionBase, ObservationBase

class MyCustomAction(ActionBase):
    # Define action parameters
    pass

class MyCustomObservation(ObservationBase):
    # Define observation data
    pass

class MyCustomTool(Tool):
    def execute(self, action: MyCustomAction) -> MyCustomObservation:
        # Implement tool logic
        pass
```

3. Add tests in the corresponding test directory
4. Update `__init__.py` to export your tool
5. Add examples demonstrating usage

### Code Standards

- **Type Annotations**: All functions must have complete type annotations
- **Documentation**: Use docstrings for public APIs, avoid redundant comments
- **Error Handling**: Implement proper error handling with meaningful messages
- **Testing**: Write tests for new functionality, aim for good coverage
- **Formatting**: Code must pass `ruff` formatting and linting

### Commit Guidelines

- Use conventional commit messages
- Include `Co-authored-by: openhands <openhands@all-hands.dev>` in commit messages
- Run pre-commit hooks before committing
- Keep commits focused and atomic

## Package Management

This project uses `uv` for fast, reliable dependency management:

```bash
# Add runtime dependency
uv add package-name

# Add development dependency
uv add --dev package-name

# Update all dependencies
uv lock --upgrade

# Install from lock file
uv sync

# Install development dependencies
uv sync --dev
```

## License

This project is part of the OpenHands ecosystem. Please refer to the main OpenHands repository for licensing information.
