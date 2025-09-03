"""Advanced example showing explicit executor usage and custom glob tool."""

import glob
import os

from pydantic import Field, SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    EventType,
    LLMConfig,
    LLMConvertibleEvent,
    Message,
    TextContent,
    Tool,
    get_logger,
)
from openhands.sdk.tool import ActionBase, ObservationBase, ToolExecutor
from openhands.tools import (
    BashExecutor,
    FileEditorTool,
    execute_bash_tool,
)


logger = get_logger(__name__)


# Define the Glob tool action and observation schemas
class GlobAction(ActionBase):
    """Schema for glob pattern matching."""

    pattern: str = Field(
        description="The glob pattern to match files (e.g., '**/*.js', 'src/**/*.ts')"
    )
    path: str = Field(
        default=".",
        description=(
            "The directory (absolute path) to search in. "
            "Defaults to the current working directory."
        ),
    )


class GlobObservation(ObservationBase):
    """Schema for glob pattern matching results."""

    files: list[str] = Field(description="List of matching file paths")
    count: int = Field(description="Number of files found")
    pattern: str = Field(description="The pattern that was searched")
    search_path: str = Field(description="The path that was searched")


# Define the Glob tool executor
class GlobExecutor(ToolExecutor[GlobAction, GlobObservation]):
    """Executor for glob pattern matching."""

    def __call__(self, action: GlobAction) -> GlobObservation:
        """Execute glob pattern matching."""
        search_path = os.path.abspath(action.path)
        pattern_path = os.path.join(search_path, action.pattern)

        # Use glob to find matching files
        matching_files = glob.glob(pattern_path, recursive=True)

        # Sort by modification time (most recent first)
        matching_files.sort(
            key=lambda f: os.path.getmtime(f) if os.path.exists(f) else 0, reverse=True
        )

        # Limit to first 100 results
        matching_files = matching_files[:100]

        return GlobObservation(
            files=matching_files,
            count=len(matching_files),
            pattern=action.pattern,
            search_path=search_path,
        )


# Tool description
_GLOB_DESCRIPTION = """Fast file pattern matching tool.
* Supports glob patterns like "**/*.js" or "src/**/*.ts"
* Use this tool when you need to find files by name patterns
* Returns matching file paths sorted by modification time
* Only the first 100 results are returned. Consider narrowing your search with stricter glob patterns or provide path parameter if you need more results.
* When you are doing an open ended search that may require multiple rounds of globbing and grepping, use the Agent tool instead
"""  # noqa: E501

# Create the glob tool using explicit executor
glob_executor = GlobExecutor()
glob_tool = Tool(
    name="glob",
    description=_GLOB_DESCRIPTION,
    input_schema=GlobAction,
    output_schema=GlobObservation,
    executor=glob_executor,
)


# Configure LLM
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."
llm = LLM(
    config=LLMConfig(
        model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
        base_url="https://llm-proxy.eval.all-hands.dev",
        api_key=SecretStr(api_key),
    )
)

# Tools - demonstrating both simplified and advanced patterns
cwd = os.getcwd()

# Advanced pattern: explicit executor creation and reuse
bash_executor = BashExecutor(working_dir=cwd)
bash_tool_advanced = execute_bash_tool.set_executor(executor=bash_executor)

tools: list[Tool] = [
    # Simplified pattern
    FileEditorTool(),
    # Advanced pattern with explicit executor
    bash_tool_advanced,
    # Custom tool with explicit executor
    glob_tool,
]

# Agent
agent = Agent(llm=llm, tools=tools)

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: EventType):
    logger.info(f"Found a conversation message: {str(event)[:200]}...")
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


conversation = Conversation(agent=agent, callbacks=[conversation_callback])

conversation.send_message(
    message=Message(
        role="user",
        content=[
            TextContent(
                text=(
                    "Hello! Can you use the glob tool to find all Python files "
                    "in this project, then create a summary file listing them? "
                    "Use the pattern '**/*.py' to search."
                )
            )
        ],
    )
)
conversation.run()

print("=" * 100)
print("Conversation finished. Got the following LLM messages:")
for i, message in enumerate(llm_messages):
    print(f"Message {i}: {str(message)[:200]}")

print("=" * 100)
print("This example demonstrates:")
print("1. Simplified pattern: FileEditorTool() - direct instantiation")
print("2. Advanced pattern: explicit BashExecutor creation and reuse")
print("3. Custom tool: GlobTool with explicit executor definition")
