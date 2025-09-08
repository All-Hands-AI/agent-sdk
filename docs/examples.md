# Examples

Run with uv:
```bash
uv run python examples/hello_world.py
uv run python examples/hello_world_with_registry.py
uv run python examples/confirmation_mode_example.py
uv run python examples/advanced_tools_with_grep.py
uv run python examples/microagent_activation.py
```

Example index
- hello_world.py — minimal agent with Bash + FileEditor tools
- hello_world_with_registry.py — using LLMRegistry for reuse
- confirmation_mode_example.py — preview/approve actions before execution
- advanced_tools_with_grep.py — custom Tool with explicit BashExecutor
- microagent_activation.py — microagents (repo + knowledge) and triggers
