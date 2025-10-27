# Development Guide

This guide covers how to set up the development environment and contribute to the OpenHands Agent SDK.

## Prerequisites

- Python 3.12+
- `uv` package manager (version 0.8.13+)

## Setup

Clone the repository and install dependencies:

```bash
git clone https://github.com/OpenHands/agent-sdk.git
cd agent-sdk
make build  # Install dependencies and setup development environment
```

This will install all packages in development mode and set up pre-commit hooks.

## Code Quality

We use several tools to maintain code quality:

### Formatting

```bash
make format  # Format all code
```

### Linting

```bash
make lint  # Lint all code
```

### Pre-commit Hooks

Pre-commit hooks run automatically on commit and include:
- Type checking with `pyright`
- Linting and formatting with `ruff`

To run all pre-commit hooks manually:

```bash
uv run pre-commit run --all-files
```

To run pre-commit on specific files:

```bash
uv run pre-commit run --files <filepath>
```

## Testing

### Run All Tests

```bash
uv run pytest
```

### Run Specific Test Suite

```bash
uv run pytest tests/sdk/          # SDK tests
uv run pytest tests/tools/        # Tools tests
uv run pytest tests/workspace/    # Workspace tests
```

### Run Specific Test File

```bash
uv run pytest tests/sdk/test_conversation.py
```

### Run with Coverage

```bash
uv run pytest --cov=openhands --cov-report=html
```

## Project Structure

```
agent-sdk/
├── openhands-sdk/          # Core SDK package
├── openhands-tools/        # Built-in tools package
├── openhands-workspace/    # Workspace management package
├── openhands-agent-server/ # Agent server package
├── examples/               # Usage examples
├── tests/                  # Test suites
└── docs/                   # Documentation (if any)
```

## Contributing

1. Create a new branch for your feature or bugfix
2. Make your changes
3. Run tests and code quality checks
4. Commit your changes (pre-commit hooks will run automatically)
5. Push to your fork and create a pull request

For more details on contributing, see the main [GitHub repository](https://github.com/OpenHands/agent-sdk).

## Documentation

For detailed SDK documentation, visit [https://docs.openhands.dev/sdk](https://docs.openhands.dev/sdk).

## Community

- [Join Slack](https://openhands.dev/joinslack) - Connect with the OpenHands community
- [GitHub Issues](https://github.com/OpenHands/agent-sdk/issues) - Report bugs or request features
