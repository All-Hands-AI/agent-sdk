# Getting Started

This guide shows how to create a simple agent that can run bash commands and edit files.

Prerequisites
- Python 3.12+
- uv installed
- A LiteLLM proxy API key set in LITELLM_API_KEY

Install
```bash
make build
```

**Hello World agent**

```python
import os
from pydantic import SecretStr
from openhands.sdk import Agent, Conversation, LLM, Message, TextContent, Tool
from openhands.tools import BashTool, FileEditorTool

api_key = os.getenv("ANTHROPIC_API_KEY")
llm = LLM(
    model="anthropic/claude-sonnet-4-20250514",
    api_key=SecretStr(api_key),
)

tools: list[Tool] = [BashTool.create(working_dir=os.getcwd()), FileEditorTool.create()]
agent = Agent(llm=llm, tools=tools)
conv = Conversation(agent=agent)
conv.send_message(Message(role="user", content=[TextContent(text="Create hello.py printing Hello")]))
conv.run()
```

Run examples

```bash
uv run python examples/1_hello_world.py
```
