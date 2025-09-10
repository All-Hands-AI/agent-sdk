# OpenHands Agent SDK (V1)

A clean, modular SDK for building AI agents. This repository provides two Python packages:

- openhands.sdk — core agent framework (agent, conversation, context, LLM, events, tools API)
- openhands.tools — production-ready tool implementations (Bash, File Editor, Task Tracker)

Goals:
- Simple mental model: short, focused modules with clear responsibilities
- Zero magic: explicit configuration over implicit behavior

Quick start

```bash
# install deps
make build

# run an example
uv run python examples/hello_world.py

# run tests
uv run pytest
```

Core concepts
- Agent: orchestrates LLM + tools to take actions
- Conversation: stateful driver for user <-> agent interaction
- Tools: strongly-typed actions + observations (input_schema/output_schema)
- LLM: thin adapter with registry for reuse across services
- Context: microagents and knowledge that condition the agent

## Architecture Documentation

Comprehensive architecture documentation is available in the [`architecture/`](./architecture/) folder:

- **[Overview](./architecture/overview.md)** - High-level component interactions and design principles
- **[Tool System](./architecture/tool.md)** - Tool framework, built-ins, runtime tools, and MCP integration  
- **[Agent Architecture](./architecture/agent.md)** - Agent execution flow, system prompts, and context management
- **[LLM Integration](./architecture/llm.md)** - Provider support, message types, and advanced features
- **[Conversation System](./architecture/conversation.md)** - State management, event system, and persistence

## Additional Documentation

- **[Getting Started](./getting-started.md)** - Step-by-step setup guide
- **[Examples](./examples.md)** - Code examples and use cases  
- **[MCP Integration](./mcp.md)** - Model Context Protocol integration guide
- **[Context System](./context/README.md)** - Context management and microagents
