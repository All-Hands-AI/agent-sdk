"""Simplified tests for the automated TODO management example."""

import importlib.util
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# Mock the openhands modules before importing
sys.modules["openhands"] = MagicMock()
sys.modules["openhands.sdk"] = MagicMock()
sys.modules["openhands.tools"] = MagicMock()
sys.modules["openhands.tools.execute_bash"] = MagicMock()
sys.modules["openhands.tools.str_replace_editor"] = MagicMock()

# Add the example directory to Python path
example_dir = Path(__file__).parent.parent
sys.path.insert(0, str(example_dir))


spec = importlib.util.spec_from_file_location(
    "automated_todo_management",
    example_dir / "20_automated_todo_management.py",
)
assert spec is not None, "Could not load module spec"
assert spec.loader is not None, "Module spec has no loader"
todo_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(todo_module)

# Import the classes
TodoItem = todo_module.TodoItem
TodoManager = todo_module.TodoManager


class TestTodoItem:
    """Test the TodoItem dataclass."""

    def test_todo_item_creation(self):
        """Test creating a TodoItem."""
        todo = TodoItem(
            file_path="test.py",
            line_number=10,
            todo_text="Fix this bug",
            context="def function():\n    # TODO(openhands): Fix this bug\n    pass",
        )

        assert todo.file_path == "test.py"
        assert todo.line_number == 10
        assert todo.todo_text == "Fix this bug"
        assert "Fix this bug" in todo.context

    def test_unique_id_generation(self):
        """Test that unique IDs are generated correctly."""
        todo1 = TodoItem(
            file_path="test.py",
            line_number=10,
            todo_text="Fix this bug",
            context="some context",
        )
        todo2 = TodoItem(
            file_path="test.py",
            line_number=20,
            todo_text="Fix this bug",
            context="some context",
        )

        # Same file and text but different lines should have different IDs
        assert todo1.unique_id != todo2.unique_id


class TestTodoManager:
    """Test the unified TodoManager class."""

    def test_manager_initialization(self):
        """Test TodoManager initialization."""
        with patch("openhands.sdk.LLM") as mock_llm:
            manager = TodoManager(
                repo_path="/test/repo",
                repo_owner="test",
                repo_name="test",
                github_token="fake_token",
                llm=mock_llm,
            )

            assert manager.repo_path == Path("/test/repo")
            assert manager.repo_owner == "test"
            assert manager.repo_name == "test"
            assert manager.github_token == "fake_token"

    def test_scan_for_todos(self):
        """Test scanning for TODOs in a temporary directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            test_file = Path(temp_dir) / "test.py"
            test_file.write_text("""
def example_function():
    # TODO(openhands): Implement error handling
    pass

def another_function():
    # TODO(openhands): Add validation
    return True
""")

            with patch("openhands.sdk.LLM") as mock_llm:
                manager = TodoManager(
                    repo_path=temp_dir,
                    repo_owner="test",
                    repo_name="test",
                    github_token="fake_token",
                    llm=mock_llm,
                )

                todos = manager.scan_todos()

                # Should find 2 TODOs
                assert len(todos) == 2
                assert any("error handling" in todo.todo_text for todo in todos)
                assert any("validation" in todo.todo_text for todo in todos)

    def test_dry_run_mode(self):
        """Test that dry run mode doesn't make actual changes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.py"
            test_file.write_text("# TODO(openhands): Test todo\npass")

            with patch("openhands.sdk.LLM") as mock_llm:
                manager = TodoManager(
                    repo_path=temp_dir,
                    repo_owner="test",
                    repo_name="test",
                    github_token="fake_token",
                    llm=mock_llm,
                )

                # Mock the GitHub API calls
                with patch.object(manager, "create_pull_request") as mock_create_pr:
                    result = manager.run(dry_run=True)

                    # Should not create any PRs in dry run mode
                    mock_create_pr.assert_not_called()

                    # Should still return results
                    assert "status" in result
                    assert "processed" in result
                    assert result["status"] == "success"

    def test_basic_functionality(self):
        """Test basic functionality without external dependencies."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test file with TODO
            test_file = Path(temp_dir) / "test.py"
            test_file.write_text("# TODO(openhands): Test todo\npass")

            with patch("openhands.sdk.LLM") as mock_llm:
                manager = TodoManager(
                    repo_path=temp_dir,
                    repo_owner="test",
                    repo_name="test",
                    github_token="fake_token",
                    llm=mock_llm,
                )

                # Test that we can scan and find TODOs
                todos = manager.scan_todos()
                assert len(todos) == 1
                assert todos[0].todo_text == "Test todo"

                # Test dry run
                result = manager.run(dry_run=True)
                assert result["status"] == "success"
                assert result["processed"] == 0  # No actual processing in dry run


if __name__ == "__main__":
    pytest.main([__file__])
