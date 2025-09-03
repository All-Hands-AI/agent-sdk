from pydantic import BaseModel, Field

from openhands.core.llm.message import Message, TextContent

from .microagents import MicroagentKnowledge
from .utils import render_microagent_info


class MessageContext(BaseModel):
    """Contextual information for EACH user message.

    Typically including: the microagents triggered by the user's input
    """

    activated_microagents: list[MicroagentKnowledge] = Field(
        default_factory=list,
        description=(
            "List of microagents that have been activated based on the user's input"
        ),
    )

    def render(self, prompt_dir: str) -> list[Message]:
        """Renders the environment context into a string using the provided PromptManager."""  # noqa: E501
        formatted_text = render_microagent_info(
            prompt_dir=prompt_dir,
            triggered_agents=self.activated_microagents,
        )
        return [Message(role="user", content=[TextContent(text=formatted_text)])]
