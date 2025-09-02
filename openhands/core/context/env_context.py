from pydantic import BaseModel, Field

from openhands.core.context.utils.prompt import render_microagent_info
from openhands.core.llm.message import TextContent

from .microagents import MicroagentKnowledge
from .utils import render_additional_info


class RuntimeInfo(BaseModel):
    date: str = Field(description="Current date in YYYY-MM-DD format")
    available_hosts: dict[str, int] = Field(
        default_factory=dict, description="Available hosts for agents to deploy to"
    )
    additional_agent_instructions: str = Field(
        default="",
        description="Additional instructions for the agent to follow during the "
        "conversation",
    )
    custom_secrets_descriptions: dict[str, str] = Field(
        default_factory=dict,
        description="Descriptions of custom secrets available to the agent",
    )
    working_dir: str = Field(
        default="", description="Current working directory of the agent"
    )


class RepositoryInfo(BaseModel):
    """Information about a GitHub repository that has been cloned."""

    repo_name: str | None = Field(
        None, description="Name of the repository, e.g., 'username/repo'"
    )
    repo_directory: str | None = Field(
        None, description="Local directory path where the repository is cloned"
    )
    branch_name: str | None = Field(
        None, description="Current branch name of the repository"
    )


class ConversationInstructions(BaseModel):
    """Optional instructions the agent must follow throughout the conversation
    while addressing the user's initial task

    Examples include

        1. Resolver instructions: you're responding to GitHub issue #1234, make
           sure to open a PR when you are done
        2. Slack instructions: make sure to check whether any of the context
           attached is relevant to the task <context_messages>
    """

    content: str = Field(
        default="",
        description="Instructions for the agent to follow during the conversation",
    )


class EnvContext(BaseModel):
    """Contextual information about the user's environment, including: repository,
    runtime environment, and conversation instructions.

    This is typically provided at the start of a session and send to the LLM as
    part of the initial prompt.
    """

    repository_info: RepositoryInfo | None = Field(
        None, description="Information about the cloned GitHub repository"
    )
    repository_instructions: str | None = Field(
        None,
        description="Additional instructions specific to the repository, e.g., "
        "relevant files or areas to focus on",
    )
    runtime_info: RuntimeInfo | None = Field(
        None, description="Information about the current runtime environment"
    )
    conversation_instructions: ConversationInstructions | None = Field(
        None,
        description="Optional instructions the agent must follow throughout the "
        "conversation while addressing the user's initial task",
    )
    activated_microagents: list[MicroagentKnowledge] = Field(
        default_factory=list,
        description=(
            "List of microagents that have been activated based on the user's input"
        ),
    )

    def render(self, prompt_dir: str) -> list[TextContent]:
        """Renders the environment context into a string using the provided PromptManager."""  # noqa: E501
        message_content = []
        # Build the workspace context information
        if (
            self.repository_info
            or self.runtime_info
            or self.repository_instructions
            or self.conversation_instructions
        ):
            formatted_workspace_text = render_additional_info(
                prompt_dir=prompt_dir,
                repository_info=self.repository_info,
                runtime_info=self.runtime_info,
                conversation_instructions=self.conversation_instructions,
                repo_instructions=self.repository_instructions,
            )
            message_content.append(TextContent(text=formatted_workspace_text))

        # Add microagent knowledge if present
        if self.activated_microagents:
            formatted_microagent_text = render_microagent_info(
                prompt_dir=prompt_dir,
                triggered_agents=self.activated_microagents,
            )
            message_content.append(TextContent(text=formatted_microagent_text))
        return message_content
