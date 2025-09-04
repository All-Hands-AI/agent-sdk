import os
import sys
from abc import ABC, abstractmethod
from types import MappingProxyType

from openhands.sdk.context.agent_context import AgentContext
from openhands.sdk.conversation import ConversationCallbackType, ConversationState
from openhands.sdk.llm import LLM
from openhands.sdk.logger import get_logger
from openhands.sdk.tool import Tool


logger = get_logger(__name__)


class AgentBase(ABC):
    def __init__(
        self,
        llm: LLM,
        tools: list[Tool],
        agent_context: AgentContext | None = None,
    ) -> None:
        """Initializes a new instance of the Agent class.

        Agent should be Stateless: every step only relies on:
        1. input ConversationState
        2. LLM/tools/agent_context that were given in __init__
        """
        self._llm = llm
        self._agent_context = agent_context

        # Load tools into an immutable dict
        _tools_map = {}
        for tool in tools:
            if tool.name in _tools_map:
                raise ValueError(f"Duplicate tool name: {tool.name}")
            logger.debug(f"Registering tool: {tool}")
            _tools_map[tool.name] = tool
        self._tools = MappingProxyType(_tools_map)

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
    def llm(self) -> LLM:
        """Returns the LLM instance used by the Agent."""
        return self._llm

    @property
    def tools(self) -> MappingProxyType[str, Tool]:
        """Returns an immutable mapping of available tools from name."""
        return self._tools

    @property
    def agent_context(self) -> AgentContext | None:
        """Returns the agent context used by the Agent."""
        return self._agent_context

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
