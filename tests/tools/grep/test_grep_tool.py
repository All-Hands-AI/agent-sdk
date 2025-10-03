"""Tests for GrepTool subclass."""

import tempfile
from pathlib import Path
from uuid import uuid4

from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.llm import LLM
from openhands.sdk.workspace import LocalWorkspace
from openhands.tools.grep import GrepAction, GrepObservation, GrepTool


def _create_test_conv_state(temp_dir: str) -> ConversationState:
    """Helper to create a test conversation state."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm")
    agent = Agent(llm=llm, tools=[])
    return ConversationState.create(
        id=uuid4(),
        agent=agent,
        workspace=LocalWorkspace(working_dir=temp_dir),
    )


def test_grep_tool_initialization():
    """Test that GrepTool initializes correctly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = GrepTool.create(conv_state)
        tool = tools[0]

        # Check that the tool has the correct name and properties
        assert tool.name == "grep"
        assert tool.executor is not None
        assert tool.action_type == GrepAction
        assert tool.observation_type == GrepObservation


def test_grep_tool_invalid_working_dir():
    """Test that GrepTool raises error for invalid working directory."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm")
    agent = Agent(llm=llm, tools=[])
    conv_state = ConversationState.create(
        id=uuid4(),
        agent=agent,
        workspace=LocalWorkspace(working_dir="/nonexistent/directory"),
    )

    try:
        GrepTool.create(conv_state)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "is not a valid directory" in str(e)


def test_grep_tool_basic_search():
    """Test that GrepTool can search for basic patterns."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test files with content
        test_files = {
            "app.py": "def main():\n    print('Hello world')\n    return 0",
            "utils.py": "def helper():\n    print('Helper function')\n    return True",
            "config.json": '{"name": "test", "debug": true}',
        }

        for file_path, content in test_files.items():
            (Path(temp_dir) / file_path).write_text(content)

        conv_state = _create_test_conv_state(temp_dir)
        tools = GrepTool.create(conv_state)
        tool = tools[0]

        # Search for "print" statements
        action = GrepAction(pattern="print")
        assert tool.executor is not None
        observation = tool.executor(action)

        assert isinstance(observation, GrepObservation)
        assert observation.error is None
        assert len(observation.matches) == 2  # Two print statements
        assert observation.pattern == "print"
        assert observation.search_path == temp_dir
        assert not observation.truncated

        # Check that matches contain expected information
        for match in observation.matches:
            assert "file_path" in match
            assert "line_number" in match
            assert "line_content" in match
            assert "print" in str(match["line_content"])


def test_grep_tool_regex_patterns():
    """Test that GrepTool handles regex patterns correctly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test file with various function definitions
        content = """
def function_one():
    pass

def function_two():
    pass

class MyClass:
    def method_one(self):
        pass
"""
        (Path(temp_dir) / "code.py").write_text(content)

        conv_state = _create_test_conv_state(temp_dir)
        tools = GrepTool.create(conv_state)
        tool = tools[0]

        # Search for function definitions using regex
        action = GrepAction(pattern=r"def\s+\w+")
        assert tool.executor is not None
        observation = tool.executor(action)

        assert observation.error is None
        assert len(observation.matches) == 3  # Three function definitions
        assert observation.pattern == r"def\s+\w+"

        # Check that all matches are function definitions
        for match in observation.matches:
            assert "def " in str(match["line_content"])


def test_grep_tool_include_filter():
    """Test that GrepTool respects include file patterns."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test files with same content but different extensions
        files_content = {
            "app.py": "print('Python file')",
            "script.js": "console.log('JavaScript file')",
            "config.json": '{"message": "JSON file"}',
        }

        for file_path, content in files_content.items():
            (Path(temp_dir) / file_path).write_text(content)

        conv_state = _create_test_conv_state(temp_dir)
        tools = GrepTool.create(conv_state)
        tool = tools[0]

        # Search for any content but only in Python files
        action = GrepAction(pattern="file", include="*.py")
        assert tool.executor is not None
        observation = tool.executor(action)

        assert observation.error is None
        assert len(observation.matches) == 1  # Only Python file
        assert observation.include_pattern == "*.py"
        assert "app.py" in observation.matches[0]["file_path"]


def test_grep_tool_specific_directory():
    """Test that GrepTool can search in specific directories."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create subdirectories with files
        src_dir = Path(temp_dir) / "src"
        src_dir.mkdir()
        (src_dir / "app.py").write_text("print('Source code')")

        tests_dir = Path(temp_dir) / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_app.py").write_text("print('Test code')")

        conv_state = _create_test_conv_state(temp_dir)
        tools = GrepTool.create(conv_state)
        tool = tools[0]

        # Search only in src directory
        action = GrepAction(pattern="print", path=str(src_dir))
        assert tool.executor is not None
        observation = tool.executor(action)

        assert observation.error is None
        assert len(observation.matches) == 1  # Only source file
        assert observation.search_path == str(src_dir)
        assert str(src_dir) in observation.matches[0]["file_path"]


def test_grep_tool_no_matches():
    """Test that GrepTool handles no matches gracefully."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a file without the search pattern
        (Path(temp_dir) / "app.py").write_text("def main():\n    return 0")

        conv_state = _create_test_conv_state(temp_dir)
        tools = GrepTool.create(conv_state)
        tool = tools[0]

        # Search for pattern that doesn't exist
        action = GrepAction(pattern="nonexistent_pattern")
        assert tool.executor is not None
        observation = tool.executor(action)

        assert observation.error is None
        assert len(observation.matches) == 0
        assert observation.pattern == "nonexistent_pattern"
        assert not observation.truncated


def test_grep_tool_invalid_regex():
    """Test that GrepTool handles invalid regex patterns."""
    with tempfile.TemporaryDirectory() as temp_dir:
        (Path(temp_dir) / "app.py").write_text("def main(): pass")

        conv_state = _create_test_conv_state(temp_dir)
        tools = GrepTool.create(conv_state)
        tool = tools[0]

        # Use invalid regex pattern
        action = GrepAction(pattern="[invalid")
        assert tool.executor is not None
        observation = tool.executor(action)

        assert observation.error is not None
        assert "Invalid regex pattern" in observation.error
        assert len(observation.matches) == 0


def test_grep_tool_invalid_directory():
    """Test that GrepTool handles invalid search directories."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = GrepTool.create(conv_state)
        tool = tools[0]

        # Search in non-existent directory
        action = GrepAction(pattern="test", path="/nonexistent/directory")
        assert tool.executor is not None
        observation = tool.executor(action)

        assert observation.error is not None
        assert "is not a valid directory" in observation.error
        assert len(observation.matches) == 0


def test_grep_tool_hidden_files_excluded():
    """Test that GrepTool excludes hidden files and directories."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create regular and hidden files
        (Path(temp_dir) / "visible.py").write_text("print('visible')")
        (Path(temp_dir) / ".hidden.py").write_text("print('hidden')")

        # Create hidden directory with file
        hidden_dir = Path(temp_dir) / ".hidden_dir"
        hidden_dir.mkdir()
        (hidden_dir / "file.py").write_text("print('in hidden dir')")

        conv_state = _create_test_conv_state(temp_dir)
        tools = GrepTool.create(conv_state)
        tool = tools[0]

        # Search for print statements
        action = GrepAction(pattern="print")
        assert tool.executor is not None
        observation = tool.executor(action)

        assert observation.error is None
        assert len(observation.matches) == 1  # Only visible file
        assert "visible.py" in observation.matches[0]["file_path"]


def test_grep_tool_binary_files_excluded():
    """Test that GrepTool excludes binary files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create text file
        (Path(temp_dir) / "text.py").write_text("print('text file')")

        # Create binary file with mostly non-printable characters
        binary_path = Path(temp_dir) / "binary.bin"
        with open(binary_path, "wb") as f:
            # Create a file that's clearly binary (less than 70% printable)
            binary_data = bytes(range(256)) * 4  # 1024 bytes of binary data
            f.write(binary_data)

        conv_state = _create_test_conv_state(temp_dir)
        tools = GrepTool.create(conv_state)
        tool = tools[0]

        # Search for print statements
        action = GrepAction(pattern="print")
        assert tool.executor is not None
        observation = tool.executor(action)

        assert observation.error is None
        assert len(observation.matches) == 1  # Only text file
        assert "text.py" in observation.matches[0]["file_path"]


def test_grep_tool_to_llm_content():
    """Test that GrepObservation converts to LLM content correctly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test file
        (Path(temp_dir) / "test.py").write_text("print('line 1')\nprint('line 2')")

        conv_state = _create_test_conv_state(temp_dir)
        tools = GrepTool.create(conv_state)
        tool = tools[0]

        # Test successful search
        action = GrepAction(pattern="print")
        assert tool.executor is not None
        observation = tool.executor(action)

        content = observation.to_llm_content
        assert len(content) == 1
        text_content = content[0].text
        assert "Found 2 match(es) for pattern" in text_content
        assert "print" in text_content
        assert "test.py:1:" in text_content
        assert "test.py:2:" in text_content


def test_grep_tool_to_llm_content_with_include():
    """Test LLM content includes file filter information."""
    with tempfile.TemporaryDirectory() as temp_dir:
        (Path(temp_dir) / "test.py").write_text("print('test')")

        conv_state = _create_test_conv_state(temp_dir)
        tools = GrepTool.create(conv_state)
        tool = tools[0]

        # Search with include filter
        action = GrepAction(pattern="print", include="*.py")
        assert tool.executor is not None
        observation = tool.executor(action)

        content = observation.to_llm_content
        text_content = content[0].text
        assert "(filtered by '*.py')" in text_content


def test_grep_tool_to_llm_content_no_matches():
    """Test LLM content for no matches."""
    with tempfile.TemporaryDirectory() as temp_dir:
        (Path(temp_dir) / "test.py").write_text("def main(): pass")

        conv_state = _create_test_conv_state(temp_dir)
        tools = GrepTool.create(conv_state)
        tool = tools[0]

        # Search for non-existent pattern
        action = GrepAction(pattern="nonexistent")
        assert tool.executor is not None
        observation = tool.executor(action)

        content = observation.to_llm_content
        text_content = content[0].text
        assert "No matches found for pattern" in text_content
        assert "nonexistent" in text_content


def test_grep_tool_to_llm_content_error():
    """Test LLM content for error cases."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = GrepTool.create(conv_state)
        tool = tools[0]

        # Search with invalid regex
        action = GrepAction(pattern="[invalid")
        assert tool.executor is not None
        observation = tool.executor(action)

        content = observation.to_llm_content
        text_content = content[0].text
        assert "Error:" in text_content
        assert "Invalid regex pattern" in text_content


def test_grep_tool_truncation():
    """Test that GrepTool truncates results when there are too many matches."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create file with many matching lines
        lines = [f"print('line {i}')" for i in range(150)]
        content = "\n".join(lines)
        (Path(temp_dir) / "large_file.py").write_text(content)

        conv_state = _create_test_conv_state(temp_dir)
        tools = GrepTool.create(conv_state)
        tool = tools[0]

        # Search for print statements
        action = GrepAction(pattern="print")
        assert tool.executor is not None
        observation = tool.executor(action)

        assert observation.error is None
        assert len(observation.matches) == 100  # Truncated to 100
        assert observation.truncated is True

        # Check LLM content mentions truncation
        content = observation.to_llm_content
        text_content = content[0].text
        assert "Results truncated to first 100 matches" in text_content


def test_grep_tool_line_numbers():
    """Test that GrepTool reports correct line numbers."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create file with specific content
        content = "line 1\nline 2\nprint('target')\nline 4\nprint('another')\nline 6"
        (Path(temp_dir) / "test.py").write_text(content)

        conv_state = _create_test_conv_state(temp_dir)
        tools = GrepTool.create(conv_state)
        tool = tools[0]

        # Search for print statements
        action = GrepAction(pattern="print")
        assert tool.executor is not None
        observation = tool.executor(action)

        assert observation.error is None
        assert len(observation.matches) == 2

        # Check line numbers are correct
        line_numbers = [match["line_number"] for match in observation.matches]
        assert 3 in line_numbers  # First print statement
        assert 5 in line_numbers  # Second print statement


def test_grep_tool_multiple_extensions_include():
    """Test that GrepTool handles file extension filtering."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create files with different extensions
        files_content = {
            "app.py": "print('Python')",
            "script.js": "console.log('JavaScript')",
            "style.css": "/* CSS comment */",
            "config.json": '{"key": "value"}',
        }

        for file_path, content in files_content.items():
            (Path(temp_dir) / file_path).write_text(content)

        conv_state = _create_test_conv_state(temp_dir)
        tools = GrepTool.create(conv_state)
        tool = tools[0]

        # Search in Python files only
        action = GrepAction(pattern="log|print", include="*.py")
        assert tool.executor is not None
        observation = tool.executor(action)

        assert observation.error is None
        assert len(observation.matches) == 1  # Python file only
        assert observation.include_pattern == "*.py"
        assert any("app.py" in str(match["file_path"]) for match in observation.matches)

        # Search in JavaScript files only
        action = GrepAction(pattern="log|print", include="*.js")
        assert tool.executor is not None
        observation = tool.executor(action)

        assert observation.error is None
        assert len(observation.matches) == 1  # JavaScript file only
        assert observation.include_pattern == "*.js"
        assert any(
            "script.js" in str(match["file_path"]) for match in observation.matches
        )
