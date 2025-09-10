import os
import sys
from abc import ABC, abstractmethod
from typing import Annotated

from pydantic import ConfigDict, Field

from openhands.sdk.context.agent_context import AgentContext
from openhands.sdk.conversation import ConversationCallbackType, ConversationState
from openhands.sdk.llm import LLM
from openhands.sdk.logger import get_logger
from openhands.sdk.tool import Tool
from openhands.sdk.utils.discriminated_union import (
    DiscriminatedUnionMixin,
    DiscriminatedUnionType,
)


logger = get_logger(__name__)


class AgentBase(DiscriminatedUnionMixin, ABC):
    model_config = ConfigDict(
        frozen=True,
        arbitrary_types_allowed=True,
    )

    llm: LLM
    agent_context: AgentContext | None = Field(default=None)
    tools: dict[str, Tool] | list[Tool] = Field(
        default_factory=dict,
        description="Mapping of tool name to Tool instance that the agent can use."
        " If a list is provided, it should be converted to a mapping by tool name.",
    )

    @property
    def prompt_dir(self) -> str:
        """Returns the directory where this class's module file is located."""
        module = sys.modules[self.__class__.__module__]
        module_file = module.__file__  # e.g. ".../mypackage/mymodule.py"
        if module_file is None:
            raise ValueError(f"Module file for {module} is None")
        return os.path.join(os.path.dirname(module_file), "prompts")

    @property
    def name(self) -> str:
        """Returns the name of the Agent."""
        return self.__class__.__name__

    @abstractmethod
    def init_state(
        self,
        state: ConversationState,
        on_event: ConversationCallbackType,
    ) -> None:
        """Initialize the empty conversation state to prepare the agent for user
        messages.

        Typically this involves adding system message

        NOTE: state will be mutated in-place.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    @abstractmethod
    def step(
        self,
        state: ConversationState,
        on_event: ConversationCallbackType,
    ) -> None:
        """Taking a step in the conversation.

        Typically this involves:
        1. Making a LLM call
        2. Executing the tool
        3. Updating the conversation state with
            LLM calls (role="assistant") and tool results (role="tool")
        4.1 If conversation is finished, set state.agent_finished flag
        4.2 Otherwise, just return, Conversation will kick off the next step

        NOTE: state will be mutated in-place.
        """
        raise NotImplementedError("Subclasses must implement this method.")


AgentType = Annotated[AgentBase, DiscriminatedUnionType[AgentBase]]
