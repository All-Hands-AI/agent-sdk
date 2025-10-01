"""Tests for the Jinja2 template detection utility."""

import tempfile
from pathlib import Path

from openhands.agent_server.jinja_template_detector import (
    find_jinja_template_directories,
    get_jinja_template_data_files,
    validate_template_directories,
)


def test_find_jinja_template_directories():
    """Test that the function correctly finds directories with .j2 files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test directory structure
        (temp_path / "openhands" / "sdk" / "agent" / "prompts").mkdir(parents=True)
        (temp_path / "openhands" / "sdk" / "context" / "prompts").mkdir(parents=True)
        (temp_path / "openhands" / "tools").mkdir(parents=True)
        (temp_path / "other" / "package").mkdir(parents=True)

        # Create .j2 files
        (temp_path / "openhands" / "sdk" / "agent" / "prompts" / "test1.j2").write_text(
            "template1"
        )
        (temp_path / "openhands" / "sdk" / "agent" / "prompts" / "test2.j2").write_text(
            "template2"
        )
        (
            temp_path / "openhands" / "sdk" / "context" / "prompts" / "test3.j2"
        ).write_text("template3")

        # Create non-.j2 files (should be ignored)
        (temp_path / "openhands" / "tools" / "test.py").write_text("python code")
        (temp_path / "other" / "package" / "test4.j2").write_text(
            "template4"
        )  # Outside openhands

        # Test the function
        result = find_jinja_template_directories(temp_path)

        # Should find 2 directories (both under openhands)
        assert len(result) == 2

        # Check the results
        source_paths = [r[0] for r in result]
        dest_paths = [r[1] for r in result]

        assert (
            str(temp_path / "openhands" / "sdk" / "agent" / "prompts") in source_paths
        )
        assert (
            str(temp_path / "openhands" / "sdk" / "context" / "prompts") in source_paths
        )
        assert "openhands/sdk/agent/prompts" in dest_paths
        assert "openhands/sdk/context/prompts" in dest_paths


def test_find_jinja_template_directories_with_custom_prefix():
    """Test the function with a custom package prefix."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test directory structure
        (temp_path / "mypackage" / "templates").mkdir(parents=True)
        (temp_path / "otherpackage" / "templates").mkdir(parents=True)

        # Create .j2 files
        (temp_path / "mypackage" / "templates" / "test1.j2").write_text("template1")
        (temp_path / "otherpackage" / "templates" / "test2.j2").write_text("template2")

        # Test with custom prefix
        result = find_jinja_template_directories(temp_path, package_prefix="mypackage")

        # Should find only 1 directory (under mypackage)
        assert len(result) == 1
        assert result[0][1] == "mypackage/templates"


def test_exclude_patterns():
    """Test that exclude patterns work correctly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test directory structure
        (temp_path / "openhands" / "templates").mkdir(parents=True)
        (temp_path / "openhands" / ".venv" / "templates").mkdir(parents=True)
        (temp_path / "openhands" / "__pycache__" / "templates").mkdir(parents=True)

        # Create .j2 files
        (temp_path / "openhands" / "templates" / "test1.j2").write_text("template1")
        (temp_path / "openhands" / ".venv" / "templates" / "test2.j2").write_text(
            "template2"
        )
        (temp_path / "openhands" / "__pycache__" / "templates" / "test3.j2").write_text(
            "template3"
        )

        # Test with default exclude patterns
        result = find_jinja_template_directories(temp_path)

        # Should find only 1 directory (excluding .venv and __pycache__)
        assert len(result) == 1
        assert result[0][1] == "openhands/templates"


def test_validate_template_directories():
    """Test the validation function."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create a valid directory with .j2 files
        valid_dir = temp_path / "valid"
        valid_dir.mkdir()
        (valid_dir / "test.j2").write_text("template")

        # Test with valid directory
        valid_dirs = [(str(valid_dir), "valid")]
        assert validate_template_directories(valid_dirs) is True

        # Test with non-existent directory
        invalid_dirs = [("/nonexistent/path", "invalid")]
        assert validate_template_directories(invalid_dirs) is False


def test_get_jinja_template_data_files():
    """Test the convenience wrapper function."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test directory structure
        (temp_path / "openhands" / "templates").mkdir(parents=True)
        (temp_path / "openhands" / "templates" / "test.j2").write_text("template")

        # Test the wrapper function
        result = get_jinja_template_data_files(temp_path, verbose=False)

        assert len(result) == 1
        assert result[0][1] == "openhands/templates"


def test_real_project_structure():
    """Test with the actual project structure."""
    # Get the project root (go up from tests/agent_server to project root)
    project_root = Path(__file__).parent.parent.parent

    # Test the function on the real project
    result = find_jinja_template_directories(project_root)

    # Should find at least the known template directories
    dest_paths = [r[1] for r in result]

    expected_paths = [
        "openhands/sdk/agent/prompts",
        "openhands/sdk/context/condenser/prompts",
        "openhands/sdk/context/prompts/templates",
    ]

    for expected_path in expected_paths:
        assert expected_path in dest_paths, (
            f"Expected path {expected_path} not found in {dest_paths}"
        )

    # Validate that all found directories actually exist and contain .j2 files
    assert validate_template_directories(result) is True
