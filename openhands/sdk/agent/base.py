import os
import re
import sys
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Annotated, Sequence, cast

from pydantic import ConfigDict, Field, PrivateAttr, field_validator

import openhands.sdk.security.analyzer as analyzer
from openhands.sdk.agent.spec import AgentSpec
from openhands.sdk.context.agent_context import AgentContext
from openhands.sdk.context.condenser import Condenser
from openhands.sdk.context.prompts.prompt import render_template
from openhands.sdk.llm import LLM
from openhands.sdk.logger import get_logger
from openhands.sdk.tool import BUILT_IN_TOOLS, Tool, ToolType
from openhands.sdk.tool.spec import ToolSpec
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
    # Runtime materialized tools; private and non-serializable
    _tools: dict[str, Tool] = PrivateAttr(default_factory=dict)

    # Back-compat: users may still pass concrete Tool instances here
    tools: dict[str, ToolType] | Sequence[ToolType] = Field(
        default_factory=dict,
        description=(
            "Mapping of tool name to Tool instance that the agent can use. "
            "If a list is provided, it should be converted to a mapping by tool name. "
            "We need to define this as ToolType for discriminated union."
        ),
    )
    # Preferred: serializable ToolSpec definitions; materialized lazily at runtime
    tool_specs: list[ToolSpec] | None = Field(default=None)

    @field_validator("tools", mode="before")
    @classmethod
    def _normalize_tools(cls, v):
        from openhands.sdk.tool import Tool

        if v is None:
            return {}
        # Already a dict[str, Tool]
        if isinstance(v, dict) and all(isinstance(t, Tool) for t in v.values()):
            return v
        # Mapping[str, Tool|dict]
        if isinstance(v, dict):
            items = v.items()
        # Iterable[Tool|dict]
        elif isinstance(v, list):
            items = (
                (
                    t.name if isinstance(t, Tool) else t.get("name"),
                    t,
                )
                for t in v
            )
        else:
            raise TypeError(
                "`tools` must be a dict[str, Tool|dict] or an iterable of Tool|dict"
            )

        user_tools: dict[str, Tool] = {}
        for name, payload in items:
            if not name or not isinstance(name, str):
                raise ValueError("Each tool must have a non-empty string `name`")
            tool = (
                payload if isinstance(payload, Tool) else Tool.model_validate(payload)
            )
            if name in user_tools:
                raise ValueError(f"Duplicate tool name: {name}")
            if tool.name != name:
                raise ValueError(
                    f"Tool key/name mismatch: key={name} vs tool.name={tool.name}"
                )
            user_tools[name] = tool
        return user_tools

    system_prompt_filename: str = Field(default="system_prompt.j2")
    system_prompt_kwargs: dict = Field(
        default_factory=dict,
        description="Optional kwargs to pass to the system prompt Jinja2 template.",
        examples=[{"cli_mode": True}],
    )
    security_analyzer: analyzer.SecurityAnalyzer | None = None
    condenser: Condenser | None = Field(
        default=None,
        description="Optional condenser to use for condensing conversation history.",
    )

    @classmethod
    def from_spec(cls, spec: AgentSpec) -> "AgentBase":
        """Create an AgentBase instance from an AgentSpec."""
        import openhands.tools  # avoid circular import
        from openhands.sdk.mcp import create_mcp_tools

        tools: list[ToolType] = []
        for tool_spec in spec.tools:
            if tool_spec.name not in openhands.tools.__dict__:
                raise ValueError(
                    f"Unknown tool name: {tool_spec.name}. Not found in openhands.tools"
                )
            tool_class = openhands.tools.__dict__[tool_spec.name]
            tool_or_tools = tool_class.create(**tool_spec.params)
            if isinstance(tool_or_tools, list):
                tools.extend(tool_or_tools)
            else:
                tools.append(tool_or_tools)

        # Check tool types
        for tool in tools:
            if not isinstance(tool, Tool):
                raise ValueError(
                    f"Tool {tool} is not an instance of 'Tool'. Got type: {type(tool)}"
                )

        # Add MCP tools if configured
        if spec.mcp_config:
            mcp_tools = create_mcp_tools(spec.mcp_config, timeout=30)
            tools.extend(mcp_tools)

        logger.info(
            f"Loaded {len(tools)} tools from spec: {[tool.name for tool in tools]}"
        )
        if spec.filter_tools_regex:
            pattern = re.compile(spec.filter_tools_regex)
            tools = [tool for tool in tools if pattern.match(tool.name)]
            logger.info(
                f"Filtered to {len(tools)} tools after applying regex filter: "
                f"{[tool.name for tool in tools]}",
            )

        return cls(
            llm=spec.llm,
            agent_context=spec.agent_context,
            tools=tools,
            system_prompt_filename=spec.system_prompt_filename,
            system_prompt_kwargs=spec.system_prompt_kwargs,
            condenser=spec.condenser,
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

    # ----- Tool materialization and access (moved from Agent) -----
    def initialize(self) -> None:
        if self._tools:
            return
        # Backward-compatible path: explicit Tool instances provided
        if isinstance(self.tools, dict) and all(
            isinstance(t, Tool) for t in self.tools.values()
        ):
            user_tools = cast(dict[str, Tool], self.tools)
            self._tools.update(self._merge_with_builtins(dict(user_tools)))
            return
        # ToolSpec-based path
        specs = getattr(self, "tool_specs", None)
        if specs:
            from openhands.sdk.tool.registry import (
                register_openhands_tools,
                resolve_many,
            )

            register_openhands_tools()
            resolved = resolve_many(specs)
            user_tools: dict[str, Tool] = {}
            for t in resolved:
                if t.name in user_tools:
                    raise ValueError(
                        f"Duplicate tool name from ToolSpec resolution: {t.name}"
                    )
                user_tools[t.name] = t
            self._tools.update(self._merge_with_builtins(user_tools))
            return
        # Default: built-ins only
        self._tools.update({t.name: t for t in BUILT_IN_TOOLS})

    def get_tools(self) -> dict[str, Tool]:
        if not self._tools:
            raise RuntimeError("Agent not initialized; call initialize() before use")
        return self._tools

    @staticmethod
    def _merge_with_builtins(user_tools: dict[str, Tool]) -> dict[str, Tool]:
        builtin_map = {t.name: t for t in BUILT_IN_TOOLS}
        to_delete: list[str] = []
        for name in set(user_tools) & set(builtin_map):
            user_tool = user_tools[name]
            builtin_tool = builtin_map[name]
            # Compare meaningful fields using model_dump
            if user_tool.model_dump() == builtin_tool.model_dump():
                to_delete.append(name)  # keep canonical built-in
            else:
                raise ValueError(f"Tool '{name}' is built-in and cannot be overridden.")
        for name in to_delete:
            del user_tools[name]
        return {**user_tools, **builtin_map}


AgentType = Annotated[AgentBase, DiscriminatedUnionType[AgentBase]]
