from __future__ import annotations

from threading import RLock
from typing import Any, Callable, Dict, List, Type

from openhands.sdk.tool import Tool
from openhands.sdk.tool.spec import ToolSpec


# A resolver produces Tool instances for given params.
Resolver = Callable[[Dict[str, Any]], List[Tool]]
"""A resolver produces Tool instances for given params.

Args:
    params: Arbitrary parameters passed to the resolver. These are typically
        used to configure the Tool instances that are created.
Returns: A list of Tool instances. Most of the time this will be a single-item list,
    but in some cases a Tool.create may produce multiple tools (e.g., BrowserToolSet).
"""

_LOCK = RLock()
_REG: Dict[str, Resolver] = {}


def _ensure_tool_list(name: str, obj: Any) -> List[Tool]:
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

    def _resolve(params: Dict[str, Any]) -> List[Tool]:
        if params:
            raise ValueError(f"Tool '{name}' is a fixed instance; params not supported")
        return [tool]

    return _resolve


def _resolver_from_subclass(name: str, cls: Type[Tool]) -> Resolver:
    create = getattr(cls, "create", None)
    if not callable(create):
        raise TypeError(
            "Unable to register tool: "
            f"Tool subclass '{cls.__name__}' must define .create(**params)"
        )

    def _resolve(params: Dict[str, Any]) -> List[Tool]:
        created = create(**params)
        tools = _ensure_tool_list(name, created)
        # Optional sanity: permit tools without executor; they'll fail at .call()
        return tools

    return _resolve


def register_tool(name: str, factory: Tool | Type[Tool]) -> None:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Tool name must be a non-empty string")

    if isinstance(factory, Tool):
        resolver = _resolver_from_instance(name, factory)
    elif isinstance(factory, type) and issubclass(factory, Tool):
        resolver = _resolver_from_subclass(name, factory)
    else:
        raise TypeError(
            "register(...) only accepts: (1) a Tool instance with .executor, or "
            "(2) a Tool subclass with .create(**params)"
        )

    with _LOCK:
        _REG[name] = resolver


def resolve_tool(tool_spec: ToolSpec) -> List[Tool]:
    with _LOCK:
        resolver = _REG.get(tool_spec.name)
    if resolver is None:
        raise KeyError(f"Tool '{tool_spec.name}' is not registered")
    return resolver(tool_spec.params)


def list_registered_tools() -> List[str]:
    with _LOCK:
        return list(_REG.keys())
