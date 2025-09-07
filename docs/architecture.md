# Architecture Overview

Packages
- openhands.sdk: agent, conversation, config, context, llm, tool, utils
- openhands.tools: concrete tools (bash, file editor) and executors

Design principles
- Keep functions short; minimize indentation depth
- Prefer data-structure design over branching
- Backward compatibility will not be kept; breakages will be documented

Key modules
- Agent: composes LLM with tools to decide next actions
- Conversation: drives message flow, state, and callbacks
- LLM: typed messages and a registry for reuse
- Tool: typed action/observation schemas and executors
- Context: microagents and repo/knowledge ingestion

Testing strategy
- Unit tests per package (openhands/sdk/tests, openhands/tools/tests)
- Integration tests under tests/
- Pre-commit runs ruff/pyright/pycodestyle
