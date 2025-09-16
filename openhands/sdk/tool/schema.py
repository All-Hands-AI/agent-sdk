from collections.abc import Sequence
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, create_model
from rich.text import Text

from openhands.sdk.llm import ImageContent, TextContent
from openhands.sdk.llm.message import content_to_str
from openhands.sdk.tool.security_prompt import (
    SECURITY_RISK_DESC,
    SECURITY_RISK_LITERAL,
)
from openhands.sdk.utils.visualize import display_dict


S = TypeVar("S", bound="Schema")


def py_type(spec: dict[str, Any]) -> Any:
    """Map JSON schema types to Python types."""
    t = spec.get("type")
    if t == "array":
        items = spec.get("items", {})
        inner = py_type(items) if isinstance(items, dict) else Any
        return list[inner]  # type: ignore[index]
    if t == "object":
        return dict[str, Any]
    _map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
    }
    if t in _map:
        return _map[t]
    return Any


def _process_schema_node(node, defs):
    """Recursively process a schema node to simplify and resolve $ref.

    https://www.reddit.com/r/mcp/comments/1kjo9gt/toolinputschema_conversion_from_pydanticmodel/
    https://gist.github.com/leandromoreira/3de4819e4e4df9422d87f1d3e7465c16
    """
    # Handle $ref references
    if "$ref" in node:
        ref_path = node["$ref"]
        if ref_path.startswith("#/$defs/"):
            ref_name = ref_path.split("/")[-1]
            if ref_name in defs:
                # Process the referenced definition
                return _process_schema_node(defs[ref_name], defs)

    # Start with a new schema object
    result = {}

    # Copy the basic properties
    if "type" in node:
        result["type"] = node["type"]

    # Handle anyOf (often used for optional fields with None)
    if "anyOf" in node:
        non_null_types = [t for t in node["anyOf"] if t.get("type") != "null"]
        if non_null_types:
            # Process the first non-null type
            processed = _process_schema_node(non_null_types[0], defs)
            result.update(processed)

    # Handle description
    if "description" in node:
        result["description"] = node["description"]

    # Handle object properties recursively
    if node.get("type") == "object" and "properties" in node:
        result["type"] = "object"
        result["properties"] = {}

        # Process each property
        for prop_name, prop_schema in node["properties"].items():
            result["properties"][prop_name] = _process_schema_node(prop_schema, defs)

        # Add required fields if present
        if "required" in node:
            result["required"] = node["required"]

    # Handle arrays
    if node.get("type") == "array" and "items" in node:
        result["type"] = "array"
        result["items"] = _process_schema_node(node["items"], defs)

    # Handle enum
    if "enum" in node:
        result["enum"] = node["enum"]

    return result


class Schema(BaseModel):
    """Base schema for input action / output observation."""

    __include_du_spec__ = True
    """Whether to include the _du_spec field in the serialized output.

    This is used to help with discriminated union deserialization fallback.
    When True, the model's JSON schema will be included in the serialized output
    under the `_du_spec` key. This allows deserialization to reconstruct the model
    even if the `kind` discriminator is missing or unresolvable.

    This can be especially useful in server-client scenarios where the client may not
    have all the same model classes registered as the server.
    e.g., MCPAction schema created in the server-side; openhands.tools action schemas
    (if the client doesn't have openhands.tools installed).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    @classmethod
    def to_mcp_schema(cls) -> dict[str, Any]:
        """Convert to JSON schema format compatible with MCP."""
        full_schema = cls.model_json_schema()
        # This will get rid of all "anyOf" in the schema,
        # so it is fully compatible with MCP tool schema
        return _process_schema_node(full_schema, full_schema.get("$defs", {}))

    @classmethod
    def from_mcp_schema(
        cls: type[S], model_name: str, schema: dict[str, Any]
    ) -> type["S"]:
        """Create a Schema subclass from an MCP/JSON Schema object.

        For non-required fields, we annotate as `T | None`
        so explicit nulls are allowed.
        """
        assert isinstance(schema, dict), "Schema must be a dict"
        assert schema.get("type") == "object", "Only object schemas are supported"

        props: dict[str, Any] = schema.get("properties", {}) or {}
        required = set(schema.get("required", []) or [])

        fields: dict[str, tuple] = {}
        for fname, spec in props.items():
            spec = spec if isinstance(spec, dict) else {}
            tp = py_type(spec)

            # Add description if present
            desc: str | None = spec.get("description")

            # Required → bare type, ellipsis sentinel
            # Optional → make nullable via `| None`, default None
            if fname in required:
                anno = tp
                default = ...
            else:
                anno = tp | None  # allow explicit null in addition to omission
                default = None

            fields[fname] = (
                anno,
                Field(default=default, description=desc)
                if desc
                else Field(default=default),
            )

        return create_model(model_name, __base__=cls, **fields)  # type: ignore[return-value]


class ActionBase(Schema):
    """Base schema for input action.

    We allow extra keys to support schema-first persistence, where action payloads
    may include fields from dynamically generated subclasses. Execution will
    rehydrate to the tool's declared action_type when available.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    # NOTE: We make it optional since some weaker
    # LLMs may not be able to fill it out correctly.
    # https://github.com/All-Hands-AI/OpenHands/issues/10797
    security_risk: SECURITY_RISK_LITERAL = Field(
        default="UNKNOWN", description=SECURITY_RISK_DESC
    )

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this action.

        This method can be overridden by subclasses to customize visualization.
        The base implementation displays all action fields systematically.
        """
        content = Text()

        # Display action name
        action_name = self.__class__.__name__
        content.append("Action: ", style="bold")
        content.append(action_name)
        content.append("\n\n")

        # Display all action fields systematically
        content.append("Arguments:", style="bold")
        action_fields = self.model_dump()
        content.append(display_dict(action_fields))

        return content

    @classmethod
    def to_mcp_schema(cls) -> dict[str, Any]:
        """Convert to JSON schema format compatible with MCP."""
        schema = super().to_mcp_schema()

        # We need to move the fields from ActionBase to the END of the properties
        # We use these properties to generate the llm schema for tool calling
        # and we want the ActionBase fields to be at the end
        # e.g. LLM should already outputs the argument for tools
        # BEFORE it predicts security_risk
        assert "properties" in schema, "Schema must have properties"
        for field_name in ActionBase.model_fields.keys():
            if field_name in schema["properties"]:
                v = schema["properties"].pop(field_name)
                schema["properties"][field_name] = v
        return schema


class MCPActionBase(ActionBase):
    """Base schema for MCP input action."""

    model_config = ConfigDict(extra="allow", frozen=True)

    # Collect all fields from ActionBase and its parents
    _parent_fields: frozenset[str] = frozenset(
        fname
        for base in ActionBase.__mro__
        if issubclass(base, BaseModel)
        for fname in {
            **base.model_fields,
            **base.model_computed_fields,
        }.keys()
    )

    def to_mcp_arguments(self) -> dict:
        """Dump model excluding parent ActionBase fields.

        This is used to convert this action to MCP tool call arguments.
        The parent fields (e.g., safety_risk) are not part of the MCP tool schema
        but are only used for our internal processing.
        """
        data = self.model_dump(exclude_none=True)
        for f in self._parent_fields:
            data.pop(f, None)
        return data


Action = ActionBase
"""Alias for action type. Previously a discriminated union, now a direct base type.
"""


class ObservationBase(Schema):
    """Base schema for output observation.

    Subclasses should override agent_observation for rich formatting.
    The base implementation provides a sensible fallback for schema-only
    observations to keep conversations robust when types aren't rehydrated.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    @property
    def agent_observation(self) -> Sequence[TextContent | ImageContent]:
        """Default observation shown to the agent.

        Fallback behavior:
        - If an 'output' field exists and is a non-empty string, use it.
        - Otherwise, show the serialized model data.
        """
        output = getattr(self, "output", None)
        if isinstance(output, str) and output.strip():
            return [TextContent(text=output)]
        data = self.model_dump(exclude_none=True)
        return [TextContent(text=str(data))]

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this action.

        This method can be overridden by subclasses to customize visualization.
        The base implementation displays all action fields systematically.
        """
        content = Text()
        text_parts = content_to_str(self.agent_observation)
        if text_parts:
            full_content = "".join(text_parts)
            content.append(full_content)
        else:
            content.append("[no text content]", style="dim")
        return content


Observation = ObservationBase
"""Observation type alias for clarity; no discriminated union behavior."""
