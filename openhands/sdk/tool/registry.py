import inspect
from collections.abc import Callable
from threading import RLock
from typing import Any

from openhands.sdk.tool.spec import ToolSpec
from openhands.sdk.tool.tool import Tool, ToolBase


# A resolver produces Tool instances for given params.
Resolver = Callable[[dict[str, Any]], list[Tool]]
"""A resolver produces Tool instances for given params.

Args:
    params: Arbitrary parameters passed to the resolver. These are typically
        used to configure the Tool instances that are created.
Returns: A list of Tool instances. Most of the time this will be a single-item list,
    but in some cases a Tool.create may produce multiple tools (e.g., BrowserToolSet).
"""

_LOCK = RLock()
_REG: dict[str, Resolver] = {}


def _ensure_tool_list(name: str, obj: Any) -> list[Tool]:
    if isinstance(obj, Tool):
        return [obj]
    if isinstance(obj, list) and all(isinstance(t, Tool) for t in obj):
        return obj
    raise TypeError(f"Factory '{name}' must return Tool or list[Tool], got {type(obj)}")


def _resolver_from_instance(name: str, tool: Tool) -> Resolver:
    if tool.executor is None:
        raise ValueError(
            "Unable to register tool: "
            f"Tool instance '{name}' must have a non-None .executor"
        )

    def _resolve(params: dict[str, Any]) -> list[Tool]:
        if params:
            raise ValueError(f"Tool '{name}' is a fixed instance; params not supported")
        return [tool]

    return _resolve


def _resolver_from_callable(
    name: str, factory: Callable[..., Tool | list[Tool]]
) -> Resolver:
    def _resolve(params: dict[str, Any]) -> list[Tool]:
        try:
            created = factory(**params)
        except TypeError as exc:
            raise TypeError(
                f"Unable to resolve tool '{name}': factory could not be called with "
                f"params {params}."
            ) from exc
        tools = _ensure_tool_list(name, created)
        return tools

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

    def _resolve(params: dict[str, Any]) -> list[Tool]:
        created = create(**params)
        tools = _ensure_tool_list(name, created)
        # Optional sanity: permit tools without executor; they'll fail at .call()
        return tools

    return _resolve


def register_tool(
    name: str, factory: Tool | type[ToolBase] | Callable[..., Tool | list[Tool]]
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
            "returning a Tool or list[Tool]"
        )

    with _LOCK:
        _REG[name] = resolver


def resolve_tool(tool_spec: ToolSpec) -> list[Tool]:
    with _LOCK:
        resolver = _REG.get(tool_spec.name)

    if resolver is None:
        raise KeyError(f"Tool '{tool_spec.name}' is not registered")

    return resolver(tool_spec.params)


def list_registered_tools() -> list[str]:
    with _LOCK:
        return list(_REG.keys())
