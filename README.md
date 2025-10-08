# OpenHands Agent SDK

The OpenHands SDK allows you to build things with agents that write software. For instance, some use cases include:

1. A documentation system that checks the changes made to your codebase this week and updates them
2. An SRE system that reads your server logs and your codebase, then uses this info to debug new errors that are appearing in prod
3. A customer onboarding system that takes all of their documents in unstructured format and enters information into your database

This SDK also powers [OpenHands](https://github.com/All-Hands-AI/OpenHands), an all-batteries-included coding agent that you can access through a GUI, CLI, or API.

## Hello World Example

This is what it looks like to write a program with an OpenHands agent:

```python
import os
from pydantic import SecretStr
from openhands.sdk import LLM, Conversation
from openhands.sdk.preset.default import get_default_agent

# Configure LLM
api_key = os.getenv("LLM_API_KEY")
assert api_key is not None, "LLM_API_KEY environment variable is not set."
llm = LLM(
    model="openhands/claude-sonnet-4-5-20250929",
    api_key=SecretStr(api_key),
)

# Create agent with default tools and configuration
agent = get_default_agent(
    llm=llm,
    working_dir=os.getcwd(),
    cli_mode=True,  # Disable browser tools for CLI environments
)

# Create conversation, send a message, and run
conversation = Conversation(agent=agent)
conversation.send_message("Create a Python file that prints 'Hello, World!'")
conversation.run()
```

## Installation & Quickstart

### Prerequisites

- Python 3.12+
- `uv` package manager (version 0.8.13+)

### Acquire and Set an LLM API Key

Obtain an API key from your favorite LLM provider, any [provider supported by LiteLLM](https://docs.litellm.ai/docs/providers)
is supported by the Agent SDK, although we have a set of [recommended models](https://docs.all-hands.dev/usage/llms/llms) that
work well with OpenHands agents.

If you want to get started quickly, you can sign up for the [OpenHands Cloud](https://app.all-hands.dev) and go to the
[API key page](https://app.all-hands.dev/settings/api-keys), which allows you to use most of our recommended models
with no markup -- documentation is [here](https://docs.all-hands.dev/usage/llms/openhands-llms).

Once you do this, you can `export LLM_API_KEY=xxx` to use all the examples.

### Setup

Once this is done, run the following to do a Hello World example.

```bash
# Clone the repository
git clone https://github.com/All-Hands-AI/agent-sdk.git
cd agent-sdk

# Install dependencies and setup development environment
make build

# Verify installation
uv run python examples/01_hello_world.py
```

For more detailed documentation and examples, refer to the `examples/` directory which contains comprehensive usage examples covering all major features of the SDK.

## Core Concepts

### Agents

Agents are the central orchestrators that coordinate between LLMs and tools. The SDK provides two main approaches for creating agents:

#### Using Default Presets

We recommend that you try out the default presets at first, which gives you a powerful agent with our default set of tools.

```python
from openhands.sdk.preset.default import get_default_agent

# Get a fully configured agent with default tools and settings
agent = get_default_agent(
    llm=llm,
    working_dir=os.getcwd(),
    cli_mode=True,  # Disable browser tools for CLI environments
)
```

#### Manual Agent Configuration

```python
from openhands.sdk import Agent
from openhands.sdk.tool import Tool, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool

# Register tools
register_tool("BashTool", BashTool)
register_tool("FileEditorTool", FileEditorTool)
register_tool("TaskTrackerTool", TaskTrackerTool)

# Create agent with explicit tool specifications
agent = Agent(
    llm=llm,
    tools=[
        Tool(name="BashTool", params={"working_dir": os.getcwd()}),
        Tool(name="FileEditorTool"),
        Tool(name="TaskTrackerTool", params={"save_dir": os.getcwd()}),
    ],
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
registry.add("default", llm)
llm = registry.get("default")
```

### Tools

Tools provide agents with capabilities to interact with the environment. The SDK includes several built-in tools:

- **BashTool**: Execute bash commands in a persistent shell session
- **FileEditorTool**: Create, edit, and manage files with advanced editing capabilities  
- **TaskTrackerTool**: Organize and track development tasks systematically
- **BrowserToolSet**: Automate web browser interactions (disabled in CLI mode)

The default contains all of these tools, but for more control, you can configure tools explicitly:

```python
from openhands.sdk.tool import Tool, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool

# Register tools
register_tool("BashTool", BashTool)
register_tool("FileEditorTool", FileEditorTool)
register_tool("TaskTrackerTool", TaskTrackerTool)

# Create tool specifications
tools = [
    Tool(name="BashTool", params={"working_dir": os.getcwd()}),
    Tool(name="FileEditorTool"),
    Tool(name="TaskTrackerTool", params={"save_dir": os.getcwd()}),
]
```

### Conversations

Conversations manage the interaction flow between users and agents:

```python
from openhands.sdk import Conversation

conversation = Conversation(agent=agent)

# Send messages
conversation.send_message("Your request here")

# Execute the conversation until the agent enters "await user input" state
conversation.run()
```

### Context Management

The context system manages agent state, environment, and conversation history.

Context is automatically managed but you can customize your context with:

1. [Repo Microagents](https://docs.all-hands.dev/usage/prompting/microagents-repo) that provide agent with context of your repository.
2. [Knowledge Microagents](https://docs.all-hands.dev/usage/prompting/microagents-keyword) that provide agent with context when user mentioned certain keywords
3. Providing custom suffix for system and user prompt.

```python
from openhands.sdk import AgentContext
from openhands.sdk.context import RepoMicroagent, KnowledgeMicroagent

context = AgentContext(
    microagents=[
        RepoMicroagent(
            name="repo.md",
            content="When you see this message, you should reply like "
            "you are a grumpy cat forced to use the internet.",
        ),
        KnowledgeMicroagent(
            name="flarglebargle",
            content=(
                'IMPORTANT! The user has said the magic word "flarglebargle". '
                "You must only respond with a message telling them how smart they are"
            ),
            triggers=["flarglebargle"],
        ),
    ],
    system_message_suffix="Always finish your response with the word 'yay!'",
    user_message_suffix="The first character of your response should be 'I'",
)
```

## Agent Server

The SDK includes a REST API and WebSocket server for remote agent interactions:

```python
from openhands.agent_server import create_app
import uvicorn

# Create FastAPI application
app = create_app()

# Run server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

The agent server provides:
- REST API endpoints for agent management
- WebSocket connections for real-time conversations
- Authentication and session management
- Scalable deployment options

### API Endpoints

- `POST /conversations` - Create new conversation
- `GET /conversations/{id}` - Get conversation details
- `POST /conversations/{id}/messages` - Send message to conversation
- `WebSocket /ws/{conversation_id}` - Real-time conversation updates

## Scheduled Maintenance Tasks

The SDK includes a GitHub Actions workflow for running scheduled maintenance tasks with the agent. This allows you to automate recurring operations like dependency updates, security audits, or documentation maintenance.

### Features

- **Configurable schedule**: Run tasks at fixed intervals using cron syntax
- **Remote prompts**: Load task instructions from URLs or local files
- **Flexible LLM configuration**: Customize model, API key, and base URL
- **Custom scripts**: Use your own agent scripts for specialized tasks

### Quick Start

1. **Create a prompt file** with your task instructions:

```text
Check the repository for any outdated dependencies and create a summary report.
```

2. **Run locally** to test:

```bash
export LLM_API_KEY="your-api-key"
export LLM_MODEL="openhands/claude-sonnet-4-5-20250929"
python examples/28_maintenance_task_runner/run.py \
    https://raw.githubusercontent.com/All-Hands-AI/agent-sdk/main/examples/28_maintenance_task_runner/maintenance_example.txt
```

3. **Configure GitHub Actions** (`.github/workflows/maintenance-task.yml`):
   - Set `LLM_API_KEY` secret in your repository settings
   - Optionally set `LLM_MODEL` and `LLM_BASE_URL` secrets
   - Uncomment and customize the cron schedule
   - Run manually or wait for scheduled execution

4. **Manual workflow dispatch**:
   - Go to Actions → "Scheduled Maintenance Task"
   - Click "Run workflow"
   - Provide prompt location (file path or URL)
   - Configure LLM settings as needed

### Configuration Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `AGENT_SCRIPT` | Python script to run the agent | `examples/28_maintenance_task_runner/run.py` |
| `PROMPT_LOCATION` | URL or path to prompt file | Required |
| `LLM_MODEL` | Language model to use | `openhands/claude-sonnet-4-5-20250929` |
| `LLM_API_KEY` | API key for the LLM | Required (from secrets) |
| `LLM_BASE_URL` | Optional base URL for LLM API | None |

For a complete example, see the [maintenance task runner](https://github.com/All-Hands-AI/agent-sdk/tree/main/examples/28_maintenance_task_runner).

## Development Workflow

### Environment Setup

```bash
# Initial setup
make build

# Install additional dependencies
# add `--dev` if you want to install 
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

# Type checking (included in pre-commit)
uv run pyright
```

### Testing

```bash
# Run all tests
uv run pytest

# Run specific test suite
uv run pytest tests/cross/
uv run pytest tests/sdk/
uv run pytest tests/tools/

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
