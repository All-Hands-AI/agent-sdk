import inspect
from collections.abc import Callable, Sequence
from threading import RLock
from typing import TYPE_CHECKING, Any

from openhands.sdk.tool.spec import ToolSpec
from openhands.sdk.tool.tool import Tool, ToolBase


if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState


# A resolver produces Tool instances for given params.
Resolver = Callable[[dict[str, Any], "ConversationState"], Sequence[Tool]]
"""A resolver produces Tool instances for given params.

Args:
    params: Arbitrary parameters passed to the resolver. These are typically
        used to configure the Tool instances that are created.
    conversation: Optional conversation state to get directories from.
Returns: A sequence of Tool instances. Most of the time this will be a single-item
    sequence, but in some cases a Tool.create may produce multiple tools
    (e.g., BrowserToolSet).
"""

_LOCK = RLock()
_REG: dict[str, Resolver] = {}


def _resolver_from_instance(name: str, tool: Tool) -> Resolver:
    if tool.executor is None:
        raise ValueError(
            "Unable to register tool: "
            f"Tool instance '{name}' must have a non-None .executor"
        )

    def _resolve(
        params: dict[str, Any], conv_state: "ConversationState"
    ) -> Sequence[Tool]:
        if params:
            raise ValueError(f"Tool '{name}' is a fixed instance; params not supported")
        return [tool]

    return _resolve


def _resolver_from_callable(
    name: str, factory: Callable[..., Sequence[Tool]]
) -> Resolver:
    def _resolve(
        params: dict[str, Any], conv_state: "ConversationState"
    ) -> Sequence[Tool]:
        try:
            # Try to call with conv_state parameter first
            created = factory(conv_state=conv_state, **params)
        except TypeError as exc:
            raise TypeError(
                f"Unable to resolve tool '{name}': factory could not be called with "
                f"params {params}."
            ) from exc
        if not isinstance(created, Sequence) or not all(
            isinstance(t, Tool) for t in created
        ):
            raise TypeError(
                f"Factory '{name}' must return Sequence[Tool], got {type(created)}"
            )
        return created

    return _resolve


def _is_abstract_method(cls: type, name: str) -> bool:
    try:
        attr = inspect.getattr_static(cls, name)
    except AttributeError:
        return False
    # Unwrap classmethod/staticmethod
    if isinstance(attr, (classmethod, staticmethod)):
        attr = attr.__func__
    return getattr(attr, "__isabstractmethod__", False)


def _resolver_from_subclass(name: str, cls: type[ToolBase]) -> Resolver:
    create = getattr(cls, "create", None)

    if create is None or not callable(create) or _is_abstract_method(cls, "create"):
        raise TypeError(
            "Unable to register tool: "
            f"Tool subclass '{cls.__name__}' must define .create(**params)"
            f" as a concrete classmethod"
        )

    def _resolve(
        params: dict[str, Any], conv_state: "ConversationState"
    ) -> Sequence[Tool]:
        created = create(conv_state=conv_state, **params)
        if not isinstance(created, Sequence) or not all(
            isinstance(t, Tool) for t in created
        ):
            raise TypeError(
                f"Tool subclass '{cls.__name__}' create() must return Sequence[Tool], "
                f"got {type(created)}"
            )
        # Optional sanity: permit tools without executor; they'll fail at .call()
        return created

    return _resolve


def register_tool(
    name: str, factory: Tool | type[ToolBase] | Callable[..., Sequence[Tool]]
) -> None:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Tool name must be a non-empty string")

    if isinstance(factory, Tool):
        resolver = _resolver_from_instance(name, factory)
    elif isinstance(factory, type) and issubclass(factory, ToolBase):
        resolver = _resolver_from_subclass(name, factory)
    elif callable(factory):
        resolver = _resolver_from_callable(name, factory)
    else:
        raise TypeError(
            "register_tool(...) only accepts: (1) a Tool instance with .executor, "
            "(2) a Tool subclass with .create(**params), or (3) a callable factory "
            "returning a Sequence[Tool]"
        )

    with _LOCK:
        _REG[name] = resolver


def resolve_tool(
    tool_spec: ToolSpec, conv_state: "ConversationState"
) -> Sequence[Tool]:
    with _LOCK:
        resolver = _REG.get(tool_spec.name)

    if resolver is None:
        raise KeyError(f"Tool '{tool_spec.name}' is not registered")

    return resolver(tool_spec.params, conv_state)


def list_registered_tools() -> list[str]:
    with _LOCK:
        return list(_REG.keys())
