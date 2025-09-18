import pytest
from pydantic import ValidationError

from openhands.sdk.mcp import MCPToolAction


def _parent_fields() -> frozenset[str]:
    # Create a minimal instance, then read the private attr value
    inst = MCPToolAction()
    pf = getattr(inst, "_parent_fields", None)
    assert isinstance(pf, (set, frozenset)), "Unexpected _parent_fields shape"
    return frozenset(pf)


def test_extras_are_included_then_emerge_from_to_mcp_arguments():
    a = MCPToolAction(new_field="value", dynamic=123)  # type: ignore
    out = a.to_mcp_arguments()

    # Parent fields must be gone (whatever they are)
    assert set(out).isdisjoint(_parent_fields())

    # Extras must remain
    assert out["new_field"] == "value"
    assert out["dynamic"] == 123


def test_declared_child_fields_survive():
    class Child(MCPToolAction):
        declared: int

    a = Child(declared=7)
    out = a.to_mcp_arguments()

    assert out == {"declared": 7}
    assert set(out).isdisjoint(_parent_fields())


def test_parent_fields_are_excluded_even_if_provided():
    """
    If a caller passes values for names that collide with parent fields,
    those keys should not appear in the final MCP args.
    """
    pf = list(_parent_fields())
    # Take up to 3 parent-looking keys (if there are that many)
    attempted = {k: "x" for k in pf[:3]}
    a = MCPToolAction(**attempted, extra_ok="yes")  # type: ignore
    out = a.to_mcp_arguments()

    assert "extra_ok" in out and out["extra_ok"] == "yes"
    assert set(out).isdisjoint(_parent_fields())


def test_exclude_none_behavior():
    a = MCPToolAction(keep_me="ok", drop_me=None)  # type: ignore
    out = a.to_mcp_arguments()
    assert out.get("keep_me") == "ok"
    assert "drop_me" not in out  # excluded by exclude_none=True


def test_frozen_model_is_immutable_or_skip_if_not_frozen():
    a = MCPToolAction(x=1)  # type: ignore
    with pytest.raises(ValidationError):
        a.x = 2  # type: ignore


def test_parent_fields_registry_shape():
    pf = _parent_fields()
    assert isinstance(pf, frozenset)
    assert len(pf) > 0

    class Child(MCPToolAction):
        child_only: str | None = None

    # Ensure the registry doesn't include child-only names
    assert "child_only" not in pf
