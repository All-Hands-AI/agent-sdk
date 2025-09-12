from unittest.mock import patch


# Metadata tests
def test_get_llm_metadata_basic():
    """Test basic metadata generation."""
    from openhands.sdk.llm.metadata import get_llm_metadata

    metadata = get_llm_metadata(model_name="gpt-4o", agent_name="test-agent")

    assert "trace_version" in metadata
    assert "tags" in metadata
    assert isinstance(metadata["tags"], list)
    assert len(metadata["tags"]) == 4

    # Check required tags
    tags = metadata["tags"]
    assert "model:gpt-4o" in tags
    assert "agent:test-agent" in tags
    assert any(tag.startswith("openhands_version:") for tag in tags)
    assert any(tag.startswith("openhands_tools_version:") for tag in tags)


def test_get_llm_metadata_without_tools_module():
    """Test metadata generation when openhands.tools module is not available."""
    from openhands.sdk.llm.metadata import get_llm_metadata

    # Mock builtins.__import__ to raise ModuleNotFoundError for openhands.tools
    original_import = __import__

    def mock_import(name, *args, **kwargs):
        if name == "openhands.tools":
            raise ModuleNotFoundError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        metadata = get_llm_metadata(model_name="gpt-4o", agent_name="test-agent")

    tags = metadata["tags"]
    assert "openhands_tools_version:n/a" in tags


def test_get_llm_metadata_with_tools_module():
    """Test metadata generation when openhands.tools module is available."""
    from openhands.sdk.llm.metadata import get_llm_metadata

    # Since the real openhands.tools module exists, just test that it works
    metadata = get_llm_metadata(model_name="gpt-4o", agent_name="test-agent")

    tags = metadata["tags"]
    # Check that the version is not "n/a" (meaning the module was found)
    tools_version_tag = next(
        (tag for tag in tags if tag.startswith("openhands_tools_version:")), None
    )
    assert tools_version_tag is not None
    assert not tools_version_tag.endswith(":n/a")


def test_get_llm_metadata_none_values():
    """Test metadata generation with None values for optional parameters."""
    from openhands.sdk.llm.metadata import get_llm_metadata

    metadata = get_llm_metadata(
        model_name="gpt-4o",
        agent_name="test-agent",
        session_id=None,
    )

    # Should not have session_id key
    assert "session_id" not in metadata
    assert "trace_version" in metadata
    assert "tags" in metadata


def test_get_llm_metadata_with_session_id():
    """Test metadata generation with session_id."""
    from openhands.sdk.llm.metadata import get_llm_metadata

    metadata = get_llm_metadata(
        model_name="gpt-4o",
        agent_name="test-agent",
        session_id="test-session-123",
    )

    assert metadata["session_id"] == "test-session-123"


def test_get_llm_metadata_with_all_params():
    """Test metadata generation with all parameters."""
    from openhands.sdk.llm.metadata import get_llm_metadata

    metadata = get_llm_metadata(
        model_name="claude-3-5-sonnet",
        agent_name="coding-agent",
        session_id="session-789",
    )

    assert metadata["session_id"] == "session-789"
    assert "model:claude-3-5-sonnet" in metadata["tags"]
    assert "agent:coding-agent" in metadata["tags"]
