# OpenHands Agent SDK (V1)

A clean, modular SDK for building AI agents. This repository provides two Python packages:

- openhands.sdk — core agent framework (agent, conversation, context, LLM, events, tools API)
- openhands.tools — production-ready tool implementations (Bash, File Editor)

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

Navigation
- Use the left sidebar in the docs site to explore Getting Started, Architecture, Tools, MCP Integration, and Examples.
- For a deep dive into tool internals, see Tools System.
