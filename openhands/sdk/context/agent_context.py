from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from openhands.sdk.context.microagents import (
    BaseMicroagent,
    KnowledgeMicroagent,
    MicroagentKnowledge,
    RepoMicroagent,
)
from openhands.sdk.context.utils import render_additional_info
from openhands.sdk.context.utils.prompt import render_microagent_info
from openhands.sdk.llm import Message, TextContent
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


class RuntimeInfo(BaseModel):
    date: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d"),
        description="Current date in YYYY-MM-DD format",
    )
    available_hosts: dict[str, int] = Field(
        default_factory=dict, description="Available hosts for agents to deploy to"
    )
    additional_agent_instructions: str = Field(
        default="", description="Additional instructions for the agent to follow"
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
    """Optional instructions the agent must follow throughout the conversation while addressing the user's initial task

    Examples include
        1. Resolver instructions: you're responding to GitHub issue #1234, make sure to open a PR
            when you are done
        2. Slack instructions: make sure to check whether any of the context attached
            is relevant to the task <context_messages>
    """  # noqa: E501

    content: str = Field(
        default="",
        description="Instructions for the agent to follow during the conversation",
    )


class AgentContext(BaseModel):
    """Central structure for managing prompt extension.

    AgentContext unifies all the contextual inputs that shape how the system
    extends and interprets user prompts. It combines both static environment
    details and dynamic, user-activated extensions from microagents.

    Specifically, it provides:
    - **Repository context / Repo Microagents**: Information about the active codebase,
      branches, and repo-specific instructions contributed by repo microagents.
    - **Runtime context**: Current execution environment (hosts, working
      directory, secrets, date, etc.).
    - **Conversation instructions**: Optional task- or channel-specific rules
      that constrain or guide the agent’s behavior across the session.
    - **Knowledge Microagents**: Extensible components that can be triggered by user input
      to inject knowledge or domain-specific guidance.

    Together, these elements make AgentContext the primary container responsible
    for assembling, formatting, and injecting all prompt-relevant context into
    LLM interactions.
    """  # noqa: E501

    microagents: list[BaseMicroagent] = Field(
        default_factory=list,
        description="List of available microagents that can extend the user's input.",
    )
    repository_info: RepositoryInfo | None = Field(
        default=None, description="Information about the cloned GitHub repository"
    )
    runtime_info: RuntimeInfo | None = Field(
        default=None, description="Information about the current runtime environment"
    )
    conversation_instructions: ConversationInstructions | None = Field(
        default=None,
        description=(
            "Optional instructions the agent must follow throughout "
            "the conversation while addressing the user's initial task"
        ),
    )

    @field_validator("microagents")
    @classmethod
    def _validate_microagents(cls, v: list[BaseMicroagent], info):
        if not v:
            return v
        # Check for duplicate microagent names
        seen_names = set()
        for microagent in v:
            if microagent.name in seen_names:
                raise ValueError(f"Duplicate microagent name found: {microagent.name}")
            seen_names.add(microagent.name)
        return v

    def _collect_repository_instructions(self) -> str:
        repo_instructions = ""
        # Retrieve the context of repo instructions from all repo microagents
        for microagent in self.microagents:
            if not isinstance(microagent, RepoMicroagent):
                continue
            if repo_instructions:
                repo_instructions += "\n\n"
            repo_instructions += microagent.content
        return repo_instructions

    def render_environment_context(self, prompt_dir: str) -> TextContent | None:
        """Render the environment context into a formatted string.

        This typically includes:
        - Repository information (repo name, branch name, PR number, etc.)
        - Runtime information (e.g., available hosts, current date)
        - Conversation instructions (e.g., user preferences, task details)
        - Repository-specific instructions (collected from repo microagents)
        """
        repository_instructions = self._collect_repository_instructions()
        logger.debug(f"Collected repository instructions: {repository_instructions}")
        # Build the workspace context information
        if (
            self.repository_info
            or self.runtime_info
            or repository_instructions
            or self.conversation_instructions
        ):
            # TODO(test): add a test for this as well
            formatted_workspace_text = render_additional_info(
                prompt_dir=prompt_dir,
                repository_info=self.repository_info,
                runtime_info=self.runtime_info,
                conversation_instructions=self.conversation_instructions,
                repository_instructions=repository_instructions,
            )
            return TextContent(text=formatted_workspace_text)

    def augment_user_message_with_knowledge(
        self, prompt_dir: str, user_message: Message, skip_microagent_names: list[str]
    ) -> tuple[TextContent, list[str]] | None:
        """Augment the user’s message with knowledge recalled from microagents.

        This works by:
        - Extracting the text content of the user message
        - Matching microagent triggers against the query
        - Returning formatted knowledge and triggered microagent names if relevant microagents were triggered
        """  # noqa: E501
        query = "\n".join(
            (c.text for c in user_message.content if isinstance(c, TextContent))
        ).strip()
        recalled_knowledge: list[MicroagentKnowledge] = []
        # skip empty queries
        if not query:
            return None
        # Search for microagent triggers in the query
        for microagent in self.microagents:
            if not isinstance(microagent, KnowledgeMicroagent):
                continue
            trigger = microagent.match_trigger(query)
            if trigger and microagent.name not in skip_microagent_names:
                logger.info(
                    "Microagent '%s' triggered by keyword '%s'",
                    microagent.name,
                    trigger,
                )
                recalled_knowledge.append(
                    MicroagentKnowledge(
                        name=microagent.name,
                        trigger=trigger,
                        content=microagent.content,
                    )
                )
        if recalled_knowledge:
            formatted_microagent_text = render_microagent_info(
                prompt_dir=prompt_dir,
                triggered_agents=recalled_knowledge,
            )
            return TextContent(text=formatted_microagent_text), [
                k.name for k in recalled_knowledge
            ]
