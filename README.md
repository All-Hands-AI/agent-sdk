# OpenHands Agent SDK

Build AI agents that write software. A clean, modular SDK with production-ready tools.

The OpenHands SDK allows you to build applications with agents that write software. This SDK also powers [OpenHands](https://github.com/OpenHands/OpenHands), an all-batteries-included coding agent that you can access through a GUI, CLI, or API.

## Features

- **Single Python API**: Unified interface for building coding agents with minimal boilerplate
- **Pre-defined Tools**: Built-in tools for bash commands, file editing, task tracking, and web browsing
- **REST-based Agent Server**: Deploy agents as scalable web services with WebSocket support for real-time interactions

## Why OpenHands Agent SDK?

- **Emphasis on coding**: Purpose-built for software development tasks with specialized tools and workflows
- **State-of-the-Art Performance**: Powered by advanced LLMs and optimized for real-world coding scenarios
- **Free and Open Source**: MIT licensed with an active community and transparent development

## Quick Start

### Prerequisites

- Python 3.12+
- `uv` package manager (version 0.8.13+)

### Installation

Install via PyPI:

```bash
pip install openhands-sdk        # Core SDK
pip install openhands-tools      # Built-in tools
pip install openhands-workspace  # Optional: sandboxed workspaces
pip install openhands-agent-server  # Optional: remote agent server
```

Or install from source:

```bash
git clone https://github.com/OpenHands/agent-sdk.git
cd agent-sdk
make build
```

### Get an API Key

Sign up for [OpenHands Cloud](https://app.all-hands.dev) and get your API key from the [API Keys page](https://app.all-hands.dev/settings/api-keys), or use any [LiteLLM-supported provider](https://docs.litellm.ai/docs/providers).

```bash
export LLM_API_KEY=your-api-key-here
```

### Run Your First Agent

```bash
# Try the hello world example
uv run python examples/01_standalone_sdk/01_hello_world.py
```

## Documentation

For detailed documentation, tutorials, and API reference, visit:

**[https://docs.openhands.dev/sdk](https://docs.openhands.dev/sdk)**

The documentation includes:
- [Getting Started Guide](https://docs.openhands.dev/sdk/getting-started) - Installation and setup
- [Core Concepts](https://docs.openhands.dev/sdk/core-concepts) - Agents, tools, conversations, and context
- [API Reference](https://docs.openhands.dev/sdk/api-reference) - Complete API documentation
- [Examples](https://docs.openhands.dev/sdk/examples) - Standalone SDK, remote execution, and GitHub workflows

## Examples

The `examples/` directory contains comprehensive usage examples:

- **Standalone SDK** (`examples/01_standalone_sdk/`) - Basic agent usage, custom tools, and microagents
- **Remote Agent Server** (`examples/02_remote_agent_server/`) - Client-server architecture and WebSocket connections
- **GitHub Workflows** (`examples/03_github_workflows/`) - CI/CD integration and automated workflows

## Development

### Setup

```bash
make build  # Install dependencies and setup development environment
```

### Code Quality

```bash
make format  # Format code
make lint    # Lint code
uv run pre-commit run --all-files  # Run pre-commit hooks
```

### Testing

```bash
uv run pytest  # Run all tests
uv run pytest tests/sdk/  # Run specific test suite
```

## Community

- [Slack Workspace](https://join.slack.com/t/openhands-ai/shared_invite/zt-2wkh4pklz-AILZ0gF3kBl~Eqd54NqYag) - Join the community
- [GitHub Repository](https://github.com/OpenHands/agent-sdk) - Source code and issues
- [Documentation](https://docs.openhands.dev/sdk) - Complete documentation

## License

MIT License - see [LICENSE](LICENSE) for details.
