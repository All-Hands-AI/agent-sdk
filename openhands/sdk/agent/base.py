import os
import sys
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Annotated, Sequence

from pydantic import ConfigDict, Field

from openhands.sdk.context.agent_context import AgentContext
from openhands.sdk.context.prompts.prompt import render_template
from openhands.sdk.llm import LLM
from openhands.sdk.logger import get_logger
from openhands.sdk.tool import ToolType
from openhands.sdk.utils.discriminated_union import (
    DiscriminatedUnionMixin,
    DiscriminatedUnionType,
)
from openhands.sdk.utils.pydantic_diff import pretty_pydantic_diff


if TYPE_CHECKING:
    from openhands.sdk.conversation import ConversationCallbackType, ConversationState

logger = get_logger(__name__)


class AgentBase(DiscriminatedUnionMixin, ABC):
    model_config = ConfigDict(
        frozen=True,
        arbitrary_types_allowed=True,
    )

    llm: LLM
    agent_context: AgentContext | None = Field(default=None)
    tools: dict[str, ToolType] | Sequence[ToolType] = Field(
        default_factory=dict,
        description="Mapping of tool name to Tool instance that the agent can use."
        " If a list is provided, it should be converted to a mapping by tool name."
        " We need to define this as ToolType for discriminated union.",
    )
    system_prompt_filename: str = Field(default="system_prompt.j2")
    system_prompt_kwargs: dict = Field(
        default_factory=dict,
        description="Optional kwargs to pass to the system prompt Jinja2 template.",
        examples=[{"cli_mode": True}],
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

    @property
    def system_message(self) -> str:
        """Compute system message on-demand to maintain statelessness."""
        # Prepare template kwargs, including cli_mode if available
        template_kwargs = dict(self.system_prompt_kwargs)
        if hasattr(self, "cli_mode"):
            template_kwargs["cli_mode"] = getattr(self, "cli_mode")

        system_message = render_template(
            prompt_dir=self.prompt_dir,
            template_name=self.system_prompt_filename,
            **template_kwargs,
        )
        if self.agent_context:
            _system_message_suffix = self.agent_context.get_system_message_suffix()
            if _system_message_suffix:
                system_message += "\n\n" + _system_message_suffix
        return system_message

    @abstractmethod
    def init_state(
        self,
        state: "ConversationState",
        on_event: "ConversationCallbackType",
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
        state: "ConversationState",
        on_event: "ConversationCallbackType",
    ) -> None:
        """Taking a step in the conversation.

        Typically this involves:
        1. Making a LLM call
        2. Executing the tool
        3. Updating the conversation state with
            LLM calls (role="assistant") and tool results (role="tool")
        4.1 If conversation is finished, set state.agent_status to FINISHED
        4.2 Otherwise, just return, Conversation will kick off the next step

        NOTE: state will be mutated in-place.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    def resolve_diff_from_deserialized(self, persisted: "AgentType") -> "AgentType":
        """
        Return a new AgentBase instance equivalent to `persisted` but with
        explicitly whitelisted fields (e.g. api_key) taken from `self`.
        """
        if persisted.__class__ is not self.__class__:
            raise ValueError(
                f"Cannot resolve from deserialized: persisted agent is of type "
                f"{persisted.__class__.__name__}, but self is of type "
                f"{self.__class__.__name__}."
            )

        new_llm = self.llm.resolve_diff_from_deserialized(persisted.llm)
        reconciled = persisted.model_copy(update={"llm": new_llm})

        if self.model_dump(exclude_none=True) != reconciled.model_dump(
            exclude_none=True
        ):
            raise ValueError(
                "The Agent provided is different from the one in persisted state.\n"
                f"Diff: {pretty_pydantic_diff(self, reconciled)}"
            )
        return reconciled

    def model_dump_succint(self, **kwargs):
        """Like model_dump, but excludes None fields by default."""
        if "exclude_none" not in kwargs:
            kwargs["exclude_none"] = True
        dumped = super().model_dump(**kwargs)
        # remove tool schema details for brevity
        if "tools" in dumped and isinstance(dumped["tools"], dict):
            dumped["tools"] = list(dumped["tools"].keys())
        return dumped


AgentType = Annotated[AgentBase, DiscriminatedUnionType[AgentBase]]
