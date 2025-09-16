from typing import Annotated, Any, Generic, TypeVar

from litellm import ChatCompletionToolParam, ChatCompletionToolParamFunctionChunk
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_serializer,
    field_validator,
)

from openhands.sdk.tool.schema import ActionBase, ObservationBase
from openhands.sdk.utils.discriminated_union import (
    DiscriminatedUnionMixin,
    DiscriminatedUnionType,
    kind_of,
    resolve_kind,
)


ActionT = TypeVar("ActionT", bound=ActionBase)
ObservationT = TypeVar("ObservationT", bound=ObservationBase)


class ToolAnnotations(BaseModel):
    """Annotations to provide hints about the tool's behavior.

    Based on Model Context Protocol (MCP) spec:
    https://github.com/modelcontextprotocol/modelcontextprotocol/blob/caf3424488b10b4a7b1f8cb634244a450a1f4400/schema/2025-06-18/schema.ts#L838
    """

    model_config = ConfigDict(
        frozen=True,
        # We need to define the title here to avoid conflict with MCP's ToolAnnotations
        # when both are included in the same JSON schema for openapi.json
        title="openhands.sdk.tool.tool.ToolAnnotations",
    )

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

    def close(self) -> None:
        """Close the executor and clean up resources.

        Default implementation does nothing. Subclasses should override
        this method to perform cleanup (e.g., closing connections,
        terminating processes, etc.).
        """
        pass


class Tool(DiscriminatedUnionMixin, Generic[ActionT, ObservationT]):
    """Tool that wraps an executor function with input/output validation and schema.

    - Normalize input/output schemas (class or dict) into both model+schema.
    - Validate inputs before execute.
    - Coerce outputs only if an output model is defined; else return vanilla JSON.
    - Export MCP tool description.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    name: str
    description: str
    action_type: type[ActionBase] = Field(repr=False)
    observation_type: type[ObservationBase] | None = Field(default=None, repr=False)

    annotations: ToolAnnotations | None = None
    meta: dict[str, Any] | None = None

    # runtime-only; always hidden on dumps
    executor: ToolExecutor | None = Field(default=None, repr=False, exclude=True)

    @classmethod
    def create(cls, *args, **kwargs) -> "Tool | list[Tool]":
        """Create a Tool instance OR a list of them. Placeholder for subclasses.

        This can be overridden in subclasses to provide custom initialization logic
            (e.g., typically initializing the executor with parameters).
        """
        raise NotImplementedError("Tool.create() must be implemented in subclasses")

    @computed_field(return_type=dict[str, Any], alias="input_schema")
    @property
    def input_schema(self) -> dict[str, Any]:
        return self.action_type.to_mcp_schema()

    @computed_field(return_type=dict[str, Any] | None, alias="output_schema")
    @property
    def output_schema(self) -> dict[str, Any] | None:
        return self.observation_type.to_mcp_schema() if self.observation_type else None

    @computed_field(return_type=str, alias="title")
    @property
    def title(self) -> str:
        if self.annotations and self.annotations.title:
            return self.annotations.title
        return self.name

    @field_serializer("action_type")
    def _ser_action_type(self, t: type[ActionBase]) -> str:
        # serialize as a plain kind string
        return kind_of(t)

    @field_serializer("observation_type")
    def _ser_observation_type(self, t: type[ObservationBase] | None) -> str | None:
        return None if t is None else kind_of(t)

    @field_validator("action_type", mode="before")
    @classmethod
    def _val_action_type(cls, v):
        if isinstance(v, str):
            return resolve_kind(v)
        assert isinstance(v, type) and issubclass(v, ActionBase), (
            f"action_type must be a subclass of ActionBase, but got {type(v)}"
        )
        return v

    @field_validator("observation_type", mode="before")
    @classmethod
    def _val_observation_type(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            v = resolve_kind(v)
        assert isinstance(v, type) and issubclass(v, ObservationBase), (
            f"observation_type must be a subclass of ObservationBase, but got {type(v)}"
        )
        return v

    def set_executor(self, executor: ToolExecutor) -> "Tool":
        """Create a new Tool instance with the given executor."""
        return self.model_copy(update={"executor": executor})

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
        if self.meta is not None:
            out["_meta"] = self.meta
        if self.output_schema:
            out["outputSchema"] = self.output_schema
        return out

    def to_openai_tool(self) -> ChatCompletionToolParam:
        """Convert an MCP tool to an OpenAI tool."""
        return ChatCompletionToolParam(
            type="function",
            function=ChatCompletionToolParamFunctionChunk(
                name=self.name,
                description=self.description,
                parameters=self.input_schema,
            ),
        )


ToolType = Annotated[Tool[ActionT, ObservationT], DiscriminatedUnionType[Tool]]
