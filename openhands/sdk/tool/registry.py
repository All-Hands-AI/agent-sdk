from __future__ import annotations

from threading import RLock
from typing import Any, Callable, Iterable, Protocol, cast

from pydantic import BaseModel

from openhands.sdk.tool import Tool
from openhands.sdk.tool.spec import ToolSpec


class _Resolver(Protocol):
    def __call__(self, params: dict[str, Any]) -> list[Tool]: ...


_registry: dict[str, _Resolver] = {}
_lock = RLock()


def register_tool(name: str, factory: Any) -> None:
    """Register a tool by name.

    Factory can be:
    - A Tool instance (no params allowed)
    - A class with a .create(**params) method returning Tool | list[Tool]
    - A callable(**params) returning Tool | list[Tool]
    """
    if not name or not isinstance(name, str) or not name.strip():
        raise ValueError("Tool name must be a non-empty string")

    def _ensure_list(obj: Tool | list[Tool]) -> list[Tool]:
        return [obj] if isinstance(obj, Tool) else obj

    def _make_resolver_from_tool_instance(tool: Tool) -> _Resolver:
        def _resolver(params: dict[str, Any]) -> list[Tool]:
            if params:
                raise ValueError(
                    f"Tool '{name}' is a fixed instance; params are not supported"
                )
            return [tool]

        return _resolver

    def _make_resolver_from_create(cls: Any) -> _Resolver:
        if not hasattr(cls, "create") or not callable(getattr(cls, "create")):
            raise TypeError(
                "Factory class must define a callable .create(**params) method"
            )

        def _resolver(params: dict[str, Any]) -> list[Tool]:
            created = cls.create(**params)
            result = _ensure_list(cast(Tool | list[Tool], created))
            for t in result:
                if not isinstance(t, Tool):
                    raise TypeError(
                        f"Factory for '{name}' returned non-Tool object: {type(t)}"
                    )
            return result

        return _resolver

    def _make_resolver_from_callable(fn: Callable[..., Any]) -> _Resolver:
        def _resolver(params: dict[str, Any]) -> list[Tool]:
            created = fn(**params)
            result = _ensure_list(cast(Tool | list[Tool], created))
            for t in result:
                if not isinstance(t, Tool):
                    raise TypeError(
                        f"Factory for '{name}' returned non-Tool object: {type(t)}"
                    )
            return result

        return _resolver

    if isinstance(factory, Tool):
        resolver = _make_resolver_from_tool_instance(factory)
    elif isinstance(factory, type):
        resolver = _make_resolver_from_create(factory)
    elif callable(factory):
        resolver = _make_resolver_from_callable(factory)
    else:
        raise TypeError(
            "Factory must be a Tool instance, a class with .create, or a callable"
        )

    with _lock:
        _registry[name] = resolver


def resolve(spec: ToolSpec) -> list[Tool]:
    with _lock:
        resolver = _registry.get(spec.name)
    if resolver is None:
        raise KeyError(
            f"Tool '{spec.name}' is not registered. "
            "Call register_tool(...) before resolving ToolSpec."
        )
    return resolver(spec.params)


def resolve_many(specs: Iterable[ToolSpec]) -> list[Tool]:
    out: list[Tool] = []
    for spec in specs:
        out.extend(resolve(spec))
    return out


def register_openhands_tools() -> None:
    """Register commonly used tools from openhands.tools.

    This is idempotent and safe to call multiple times.
    Only registers high-level Tool classes/toolsets that expose .create.
    """
    try:
        import openhands.tools as tools_mod  # lazy import
    except Exception:
        return

    # Explicit allowlist to avoid registering non-Tool objects
    names = [
        "BashTool",
        "FileEditorTool",
        "TaskTrackerTool",
        "BrowserToolSet",
    ]
    for n in names:
        try:
            factory = getattr(tools_mod, n)
        except AttributeError:
            continue
        try:
            register_tool(n, factory)
        except Exception:
            # Best-effort; ignore if already registered or invalid
            continue


# Optional: helper for introspection
class _RegistrySnapshot(BaseModel):
    names: list[str]


def list_registered() -> list[str]:
    with _lock:
        return list(_registry.keys())
