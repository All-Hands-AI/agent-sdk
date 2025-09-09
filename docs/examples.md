# Examples

Run with uv:
```bash
uv run python examples/1_hello_world.py
uv run python examples/2_custom_tools.py
uv run python examples/3_activate_microagent.py
uv run python examples/4_confirmation_mode_example.py
uv run python examples/5_use_llm_registry.py
uv run python examples/6_interactive_terminal_w_reasoning.py
uv run python examples/7_mcp_integration.py
uv run python examples/8_mcp_with_oauth.py
uv run python examples/9_pause_example.py
```

## Example Index

### Basic Examples
- **1_hello_world.py** — minimal agent with Bash + FileEditor tools using simplified tool pattern
- **5_use_llm_registry.py** — using LLMRegistry for LLM management and reuse
- **6_interactive_terminal_w_reasoning.py** — agent that can enter Python interactive mode and using a reasoning model (e.g., `gemini-2.5-pro`)

### Advanced Tool Usage
- **2_custom_tools.py** — advanced example showing explicit executor usage and custom grep tool
- **3_activate_microagent.py** — microagents (repo + knowledge) and activation triggers

### Interaction Modes
- **4_confirmation_mode_example.py** — preview and approve actions before execution
- **9_pause_example.py** — demonstrates pausing and resuming agent execution

### MCP Integrations
- **7_mcp_integration.py** — integrating with Model Context Protocol (MCP) tools
- **8_mcp_with_oauth.py** — MCP integration with OAuth authentication
