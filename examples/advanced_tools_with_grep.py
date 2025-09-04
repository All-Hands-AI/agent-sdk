"""Advanced example showing explicit executor usage and custom grep tool."""

import os

from pydantic import Field, SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    EventType,
    LLMConvertibleEvent,
    Message,
    TextContent,
    Tool,
    get_logger,
)
from openhands.sdk.tool import ActionBase, ObservationBase, ToolExecutor
from openhands.tools import (
    BashExecutor,
    ExecuteBashAction,
    FileEditorTool,
    execute_bash_tool,
)


logger = get_logger(__name__)


# Define the Grep tool action and observation schemas
class GrepAction(ActionBase):
    """Schema for content search using grep."""

    pattern: str = Field(description="The regex pattern to search for in file contents")
    path: str = Field(
        default=".",
        description=(
            "The directory (absolute path) to search in. "
            "Defaults to the current working directory."
        ),
    )
    include: str | None = Field(
        default=None,
        description=(
            "Optional file pattern to filter which files to search "
            "(e.g., '*.js', '*.{ts,tsx}')"
        ),
    )


class GrepObservation(ObservationBase):
    """Schema for grep search results."""

    matches: list[str] = Field(description="List of matching lines with file paths")
    files: list[str] = Field(description="List of files that had matches")
    count: int = Field(description="Number of matching lines found")
    pattern: str = Field(description="The pattern that was searched")
    search_path: str = Field(description="The path that was searched")


# Define the Grep tool executor
class GrepExecutor(ToolExecutor[GrepAction, GrepObservation]):
    """Executor for content search using bash grep commands."""

    def __init__(self, bash_executor: BashExecutor):
        """Initialize with a bash executor."""
        self.bash_executor = bash_executor

    def __call__(self, action: GrepAction) -> GrepObservation:
        """Execute content search using bash grep commands."""
        search_path = os.path.abspath(action.path)

        # Build the grep command
        grep_cmd = f"cd '{search_path}' && "

        if action.include:
            # Use find with file pattern and pipe to grep
            grep_cmd += (
                f"find . -name '{action.include}' -type f 2>/dev/null | "
                f"head -1000 | "
                f"xargs grep -H -n -E '{action.pattern}' 2>/dev/null | "
                f"head -100"
            )
        else:
            # Search all files recursively
            grep_cmd += f"grep -r -H -n -E '{action.pattern}' . 2>/dev/null | head -100"

        bash_action = ExecuteBashAction(command=grep_cmd, security_risk="LOW")

        result = self.bash_executor(bash_action)

        # Parse the output
        matches = []
        files = set()

        if result.exit_code == 0 and result.output.strip():
            for line in result.output.strip().split("\n"):
                if line.strip():
                    matches.append(line)
                    # Extract filename from grep output (format: ./path/file:line:content)  # noqa: E501
                    if ":" in line:
                        file_path = line.split(":", 1)[0].lstrip("./")
                        if file_path:
                            files.add(os.path.join(search_path, file_path))

        return GrepObservation(
            matches=matches,
            files=list(files),
            count=len(matches),
            pattern=action.pattern,
            search_path=search_path,
        )


# Tool description
_GREP_DESCRIPTION = """Fast content search tool.
* Searches file contents using regular expressions
* Supports full regex syntax (eg. "log.*Error", "function\\s+\\w+", etc.)
* Filter files by pattern with the include parameter (eg. "*.js", "*.{ts,tsx}")
* Returns matching file paths sorted by modification time.
* Only the first 100 results are returned. Consider narrowing your search with stricter regex patterns or provide path parameter if you need more results.
* Use this tool when you need to find files containing specific patterns
* When you are doing an open ended search that may require multiple rounds of globbing and grepping, use the Agent tool instead
"""  # noqa: E501

# Configure LLM
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."
llm = LLM(
    model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

# Tools - demonstrating both simplified and advanced patterns
cwd = os.getcwd()

# Advanced pattern: explicit executor creation and reuse
bash_executor = BashExecutor(working_dir=cwd)
bash_tool_advanced = execute_bash_tool.set_executor(executor=bash_executor)

# Create the grep tool using explicit executor that reuses the bash executor
grep_executor = GrepExecutor(bash_executor)
grep_tool = Tool(
    name="grep",
    description=_GREP_DESCRIPTION,
    input_schema=GrepAction,
    output_schema=GrepObservation,
    executor=grep_executor,
)

tools: list[Tool] = [
    # Simplified pattern
    FileEditorTool(),
    # Advanced pattern with explicit executor
    bash_tool_advanced,
    # Custom tool with explicit executor
    grep_tool,
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
                    "Hello! Can you use the grep tool to find all files "
                    "containing the word 'class' in this project, then create a summary file listing them? "  # noqa: E501
                    "Use the pattern 'class' to search and include only Python files with '*.py'."  # noqa: E501
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
