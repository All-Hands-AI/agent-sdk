# OpenHands Agent SDK

A clean, modular SDK for building AI agents with OpenHands. This project represents a complete architectural refactor from OpenHands V0, emphasizing simplicity, maintainability, and developer experience.

## Repository Structure

```
agent-sdk/
├── .github/
│   └── workflows/           # CI/CD workflows
│       ├── precommit.yml   # Pre-commit hook validation
│       └── tests.yml       # Test execution pipeline
├── .pre-commit-config.yaml # Pre-commit hooks configuration
├── Makefile                # Build and development commands
├── README.md               # This file
├── pyproject.toml          # Root project configuration
├── uv.lock                 # Dependency lock file
├── examples/
│   └── hello_world.py      # Getting started example
├── openhands/              # Main SDK packages
│   ├── core/               # Core SDK functionality
│   │   ├── agent/          # Agent implementations
│   │   │   ├── base.py     # Base agent interface
│   │   │   └── agent/      # Agent implementation
│   │   ├── config/         # Configuration management
│   │   │   ├── llm_config.py   # LLM configuration
│   │   │   └── mcp_config.py   # MCP configuration
│   │   ├── context/        # Context management system
│   │   │   ├── env_context.py      # Environment context
│   │   │   ├── message_context.py  # Message context
│   │   │   ├── history.py          # Conversation history
│   │   │   ├── manager.py          # Context manager
│   │   │   ├── prompt.py           # Prompt management
│   │   │   └── microagents/        # Microagent system
│   │   ├── conversation/   # Conversation management
│   │   │   ├── conversation.py # Core conversation logic
│   │   │   ├── serializer.py   # Conversation serialization
│   │   │   ├── state.py        # Conversation state
│   │   │   ├── types.py        # Type definitions
│   │   │   └── visualizer.py   # Conversation visualization
│   │   ├── llm/            # LLM integration layer
│   │   │   ├── llm.py      # Main LLM interface
│   │   │   ├── message.py  # Message handling
│   │   │   ├── metadata.py # LLM metadata
│   │   │   └── utils/      # LLM utilities
│   │   ├── tool/           # Tool system
│   │   │   ├── tool.py     # Core tool interface
│   │   │   ├── schema.py   # Tool schema definitions
│   │   │   └── builtins/   # Built-in tools
│   │   ├── utils/          # Core utilities
│   │   ├── logger.py       # Logging configuration
│   │   ├── pyproject.toml  # Core package configuration
│   │   └── tests/          # Unit tests for core
│   └── tools/              # Tool implementations
│       ├── execute_bash/   # Bash execution tool
│       ├── str_replace_editor/  # String replacement editor
│       ├── utils/          # Tool utilities
│       ├── pyproject.toml  # Tools package configuration
│       └── tests/          # Unit tests for tools
└── tests/                  # Integration tests
```

## Quick Start

```bash
# Install dependencies
make build

# Run hello world example
uv run python examples/hello_world.py

# Run tests
uv run pytest

# Run pre-commit hooks
uv run pre-commit run --all-files
```

## Development Guidelines

### Core Principles

This project follows principles of simplicity, pragmatism, and maintainability:

1. **Simplicity First**: If it needs more than 3 levels of indentation, redesign it
2. **No Special Cases**: Good code eliminates edge cases through proper data structure design
3. **Pragmatic Solutions**: Solve real problems, not imaginary ones
4. **Never Break Userspace**: Backward compatibility is sacred

### Architecture Overview

The SDK is built around two core packages:

- **`openhands/core`**: Core SDK functionality (agents, LLM, context, conversation)
- **`openhands/tools`**: Tool implementations (bash execution, file editing)

Each package is independently testable and deployable, with clear separation of concerns.

### Development Workflow

#### 1. Environment Setup

```bash
# Initial setup
make build

# Activate virtual environment (if needed)
source .venv/bin/activate
```

#### 2. Code Quality Standards

- **Type Checking**: All code must pass `pyright` type checking
- **Linting**: Code must pass `ruff` linting and formatting
- **Testing**: Maintain test coverage for new functionality
- **Documentation**: Code should be self-documenting; avoid redundant comments

#### 3. Pre-commit Workflow

Before every commit:

```bash
# Run pre-commit hooks on changed files
uv run pre-commit run --files <filepath>

# Or run on all files
uv run pre-commit run --all-files
```

#### 4. Testing Strategy

**Unit Tests**: Located in package-specific test directories
- `openhands/core/tests/` - Tests for core functionality
- `openhands/tools/tests/` - Tests for tool implementations

**Integration Tests**: Located in root `tests/` directory
- Tests that involve both core and tools packages

**Running Tests**:
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest openhands/core/tests/tool/test_tool.py

# Run with coverage
uv run pytest --cov=openhands
```

#### 5. Package Management

This project uses `uv` for dependency management:

```bash
# Add a new dependency
uv add package-name

# Add a development dependency
uv add --dev package-name

# Update dependencies
uv lock --upgrade

# Install from lock file
uv sync
```
