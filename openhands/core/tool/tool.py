import re
from typing import Any, Generic, TypeVar

from openai.types.chat import ChatCompletionToolParam
from openai.types.shared_params.function_definition import FunctionDefinition
from pydantic import BaseModel, Field

from openhands.core.tool.schema import ActionBase, ObservationBase, Schema


ActionT = TypeVar("ActionT", bound=ActionBase)
ObservationT = TypeVar("ObservationT", bound=ObservationBase)


def to_camel_case(s: str) -> str:
    parts = re.split(r"[_\-\s]+", s)
    return "".join(word.capitalize() for word in parts if word)


class ToolAnnotations(BaseModel):
    """Annotations to provide hints about the tool's behavior.

    Based on Model Context Protocol (MCP) spec:
    https://github.com/modelcontextprotocol/modelcontextprotocol/blob/caf3424488b10b4a7b1f8cb634244a450a1f4400/schema/2025-06-18/schema.ts#L838
    """

    title: str | None = Field(
        default=None, description="A human-readable title for the tool."
    )
    readOnlyHint: bool = Field(
        default=False,
        description="If true, the tool does not modify its environment. Default: false",
    )
    destructiveHint: bool = Field(
        default=True,
        description="If true, the tool may perform destructive updates to its environment. If false, the tool performs only additive updates. (This property is meaningful only when `readOnlyHint == false`) Default: true",  # noqa: E501
    )
    idempotentHint: bool = Field(
        default=False,
        description="If true, calling the tool repeatedly with the same arguments will have no additional effect on the its environment. (This property is meaningful only when `readOnlyHint == false`) Default: false",  # noqa: E501
    )
    openWorldHint: bool = Field(
        default=True,
        description="If true, this tool may interact with an 'open world' of external entities. If false, the tool's domain of interaction is closed. For example, the world of a web search tool is open, whereas that of a memory tool is not. Default: true",  # noqa: E501
    )


class ToolExecutor(Generic[ActionT, ObservationT]):
    """Executor function type for a Tool."""

    def __call__(self, action: ActionT) -> ObservationT:
        raise NotImplementedError


class Tool(Generic[ActionT, ObservationT]):
    """Tool that wraps an executor function with input/output validation and schema.

    - Normalize input/output schemas (class or dict) into both model+schema.
    - Validate inputs before execute.
    - Coerce outputs only if an output model is defined; else return vanilla JSON.
    - Export MCP tool description.
    """

    def __init__(
        self,
        *,
        name: str,
        description: str,
        input_schema: type[ActionBase] | dict[str, Any],
        output_schema: type[ObservationBase] | dict[str, Any] | None = None,
        annotations: ToolAnnotations | None = None,
        _meta: dict[str, Any] | None = None,
        executor: ToolExecutor | None = None,
    ):
        self.name = name
        self.description = description
        self.annotations = annotations
        self._meta = _meta
        self._set_input_schema(input_schema)
        self._set_output_schema(output_schema)

        self.executor = executor

    def set_executor(self, executor: ToolExecutor) -> "Tool":
        """Set or replace the executor function."""
        self.executor = executor
        return self

    def _set_input_schema(
        self, input_schema: dict[str, Any] | type[ActionBase]
    ) -> None:
        # ---- INPUT: class or dict -> model + schema
        self.action_type: type[ActionBase]
        self.input_schema: dict[str, Any]
        if isinstance(input_schema, type) and issubclass(input_schema, Schema):
            self.action_type = input_schema
            self.input_schema = input_schema.to_mcp_schema()
        elif isinstance(input_schema, dict):
            self.input_schema = input_schema
            self.action_type = ActionBase.from_mcp_schema(
                f"{to_camel_case(self.name)}Action", input_schema
            )
        else:
            raise TypeError(
                "input_schema must be ActionBase subclass or dict JSON schema"
            )

    def _set_output_schema(
        self, output_schema: dict[str, Any] | type[ObservationBase] | None
    ) -> None:
        # ---- OUTPUT: optional class or dict -> model + schema
        self.observation_type: type[ObservationBase] | None
        self.output_schema: dict[str, Any] | None
        if output_schema is None:
            self.observation_type = None
            self.output_schema = None
        elif isinstance(output_schema, type) and issubclass(output_schema, Schema):
            self.observation_type = output_schema
            self.output_schema = output_schema.to_mcp_schema()
        elif isinstance(output_schema, dict):
            self.output_schema = output_schema
            self.observation_type = ObservationBase.from_mcp_schema(
                f"{to_camel_case(self.name)}Observation", output_schema
            )
        else:
            raise TypeError(
                "output_schema must be ObservationBase subclass, dict, or None"
            )

    def call(self, action: ActionT) -> ObservationBase:
        """Validate input, execute, and coerce output.

        We always return some ObservationBase subclass, but not always the
        generic ObservationT.
        """
        if self.executor is None:
            raise NotImplementedError(f"Tool '{self.name}' has no executor")

        # Execute
        result = self.executor(action)

        # Coerce output only if we declared a model; else wrap in base ObservationBase
        if self.observation_type:
            if isinstance(result, self.observation_type):
                return result
            return self.observation_type.model_validate(result)
        else:
            # When no output schema is defined, wrap the result in ObservationBase
            if isinstance(result, ObservationBase):
                return result
            elif isinstance(result, BaseModel):
                return ObservationBase.model_validate(result.model_dump())
            elif isinstance(result, dict):
                return ObservationBase.model_validate(result)
            raise TypeError(
                "Output must be dict or BaseModel when no output schema is defined"
            )

    def to_mcp_tool(self) -> dict[str, Any]:
        out = {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }
        if self.annotations:
            out["annotations"] = self.annotations
        if self._meta is not None:
            out["_meta"] = self._meta
        if self.output_schema:
            out["outputSchema"] = self.output_schema
        return out

    def to_openai_tool(self) -> ChatCompletionToolParam:
        """Convert an MCP tool to an OpenAI tool."""
        return ChatCompletionToolParam(
            type="function",
            function=FunctionDefinition(
                name=self.name,
                description=self.description,
                parameters=self.input_schema,
                strict=False,
            ),
        )
