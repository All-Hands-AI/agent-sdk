import pathlib

from pydantic import BaseModel, Field, field_validator

from openhands.sdk.context.microagents import (
    BaseMicroagent,
    KnowledgeMicroagent,
    MicroagentKnowledge,
    RepoMicroagent,
)
from openhands.sdk.context.utils import render_template
from openhands.sdk.llm import Message, TextContent
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)

PROMPT_DIR = pathlib.Path(__file__).parent / "utils" / "prompts"


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
    system_message_suffix: str | None = Field(
        default=None, description="Optional suffix to append to the system prompt."
    )
    user_message_suffix: str | None = Field(
        default=None, description="Optional suffix to append to the user's message."
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

    def get_system_message_suffix(self) -> str | None:
        """Get the system message with repo microagent content and custom suffix.

        Custom suffix can typically includes:
        - Repository information (repo name, branch name, PR number, etc.)
        - Runtime information (e.g., available hosts, current date)
        - Conversation instructions (e.g., user preferences, task details)
        - Repository-specific instructions (collected from repo microagents)
        """
        repo_microagents = [
            m for m in self.microagents if isinstance(m, RepoMicroagent)
        ]
        logger.debug(
            f"Triggered {len(repo_microagents)} repository "
            f"microagents: {repo_microagents}"
        )
        # Build the workspace context information
        if repo_microagents:
            # TODO(test): add a test for this rendering to make sure they work
            formatted_text = render_template(
                prompt_dir=str(PROMPT_DIR),
                template_name="system_message_suffix.j2",
                repo_microagents=repo_microagents,
                system_message_suffix=self.system_message_suffix or "",
            ).strip()
            return formatted_text
        elif self.system_message_suffix and self.system_message_suffix.strip():
            return self.system_message_suffix.strip()
        return None

    def get_user_message_suffix(
        self, user_message: Message, skip_microagent_names: list[str]
    ) -> tuple[TextContent, list[str]] | None:
        """Augment the user’s message with knowledge recalled from microagents.

        This works by:
        - Extracting the text content of the user message
        - Matching microagent triggers against the query
        - Returning formatted knowledge and triggered microagent names if relevant microagents were triggered
        """  # noqa: E501

        user_message_suffix = None
        if self.user_message_suffix and self.user_message_suffix.strip():
            user_message_suffix = self.user_message_suffix.strip()

        query = "\n".join(
            (c.text for c in user_message.content if isinstance(c, TextContent))
        ).strip()
        recalled_knowledge: list[MicroagentKnowledge] = []
        # skip empty queries, but still return user_message_suffix if it exists
        if not query:
            if user_message_suffix:
                return TextContent(text=user_message_suffix), []
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
            formatted_microagent_text = render_template(
                prompt_dir=str(PROMPT_DIR),
                template_name="microagent_knowledge_info.j2",
                triggered_agents=recalled_knowledge,
            )
            if user_message_suffix:
                formatted_microagent_text += "\n" + user_message_suffix
            return TextContent(text=formatted_microagent_text), [
                k.name for k in recalled_knowledge
            ]

        if user_message_suffix:
            return TextContent(text=user_message_suffix), []
        return None
