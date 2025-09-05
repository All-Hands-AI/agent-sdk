"""Tests for MCP tool functionality."""

from unittest.mock import MagicMock

from openhands.sdk.mcp.tool import (
    MCPTool,
    MCPToolAction,
    MCPToolExecutor,
    MCPToolObservation,
    MCPToolRegistry,
)


class TestMCPToolAction:
    """Test MCPToolAction data class."""

    def test_mcp_tool_action_creation(self):
        """Test creating an MCP tool action."""
        action = MCPToolAction(
            tool_name="test_tool",
            arguments={"param1": "value1", "param2": 42},
        )

        assert action.tool_name == "test_tool"
        assert action.arguments == {"param1": "value1", "param2": 42}

    def test_mcp_tool_action_empty_arguments(self):
        """Test creating an MCP tool action with empty arguments."""
        action = MCPToolAction(tool_name="test_tool")

        assert action.tool_name == "test_tool"
        assert action.arguments == {}


class TestMCPToolObservation:
    """Test MCPToolObservation data class."""

    def test_mcp_tool_observation_success(self):
        """Test creating a successful MCP tool observation."""
        observation = MCPToolObservation(
            tool_name="test_tool",
            content="Operation completed successfully",
            is_error=False,
        )

        assert observation.tool_name == "test_tool"
        assert observation.content == "Operation completed successfully"
        assert observation.is_error is False

    def test_mcp_tool_observation_error(self):
        """Test creating an error MCP tool observation."""
        observation = MCPToolObservation(
            tool_name="test_tool",
            content="Operation failed: Invalid parameter",
            is_error=True,
            error_message="Invalid parameter",
        )

        assert observation.tool_name == "test_tool"
        assert observation.content == "Operation failed: Invalid parameter"
        assert observation.is_error is True
        assert observation.error_message == "Invalid parameter"


class TestMCPToolExecutor:
    """Test MCPToolExecutor functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = MagicMock()
        self.executor = MCPToolExecutor(mcp_client=self.mock_client)

    def test_execute_success(self):
        """Test successful tool execution."""
        # Mock successful MCP call
        mock_result = MagicMock()
        mock_result.content = [{"text": "Success result"}]
        mock_result.isError = False
        mock_result.model_dump.return_value = {
            "content": [{"text": "Success result"}],
            "isError": False,
        }

        # Mock the client's call_tool method directly
        self.mock_client.call_tool.return_value = mock_result

        action = MCPToolAction(
            tool_name="test_tool",
            arguments={"param": "value"},
        )

        observation = self.executor(action)

        assert isinstance(observation, MCPToolObservation)
        assert observation.tool_name == "test_tool"
        assert (
            observation.content
            == '{"content": [{"text": "Success result"}], "isError": false}'
        )
        assert observation.is_error is False

    def test_execute_error(self):
        """Test tool execution with error."""
        # Mock error MCP call
        mock_result = MagicMock()
        mock_result.content = [{"text": "Error occurred"}]
        mock_result.isError = True
        mock_result.model_dump.return_value = {
            "content": [{"text": "Error occurred"}],
            "isError": True,
        }

        # Mock the client's call_tool method directly
        self.mock_client.call_tool.return_value = mock_result

        action = MCPToolAction(
            tool_name="test_tool",
            arguments={"param": "value"},
        )

        observation = self.executor(action)

        assert isinstance(observation, MCPToolObservation)
        assert observation.tool_name == "test_tool"
        assert (
            observation.content
            == '{"content": [{"text": "Error occurred"}], "isError": true}'
        )
        assert observation.is_error is True

    def test_execute_exception(self):
        """Test tool execution with exception."""
        # Mock exception during execution
        self.mock_client.call_tool.side_effect = Exception("Connection failed")

        action = MCPToolAction(
            tool_name="test_tool",
            arguments={"param": "value"},
        )

        observation = self.executor(action)

        assert isinstance(observation, MCPToolObservation)
        assert observation.tool_name == "test_tool"
        assert observation.content == ""
        assert observation.is_error is True
        assert (
            observation.error_message
            and "Connection failed" in observation.error_message
        )

    def test_execute_empty_content(self):
        """Test tool execution with empty content."""
        # Mock result with empty content
        mock_result = MagicMock()
        mock_result.content = []
        mock_result.isError = False
        mock_result.model_dump.return_value = {"content": [], "isError": False}

        # Mock the client's call_tool method directly
        self.mock_client.call_tool.return_value = mock_result

        action = MCPToolAction(
            tool_name="test_tool",
            arguments={"param": "value"},
        )

        observation = self.executor(action)

        assert isinstance(observation, MCPToolObservation)
        assert observation.tool_name == "test_tool"
        assert observation.content == '{"content": [], "isError": false}'
        assert observation.is_error is False


class TestMCPTool:
    """Test MCPTool functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = MagicMock()

        # Mock tool map
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.description = "A test tool"
        mock_tool.inputSchema = {"type": "object", "properties": {}}

        self.mock_client.tool_map = {"test_tool": mock_tool}

        self.tool = MCPTool(mcp_client=self.mock_client, tool_name="test_tool")

    def test_mcp_tool_creation(self):
        """Test creating an MCP tool."""
        assert self.tool.name == "test_tool"
        assert self.tool.description == "A test tool"

    def test_create_action(self):
        """Test creating an action for the tool."""
        # Create action directly using the action type
        action = MCPToolAction(tool_name="test_tool", arguments={"param": "value"})

        assert isinstance(action, MCPToolAction)
        assert action.tool_name == "test_tool"
        assert action.arguments == {"param": "value"}

    def test_execute_action(self):
        """Test executing an action through the tool."""
        # Mock successful execution
        mock_result = MagicMock()
        mock_result.content = [{"text": "Success"}]
        mock_result.isError = False
        mock_result.model_dump.return_value = {
            "content": [{"text": "Success"}],
            "isError": False,
        }

        # Mock the client's call_tool method directly
        self.mock_client.call_tool.return_value = mock_result

        action = MCPToolAction(tool_name="test_tool", arguments={"param": "value"})

        observation = self.tool.call(action)

        assert isinstance(observation, MCPToolObservation)
        assert observation.tool_name == "test_tool"
        assert observation.is_error is False

    def test_to_openai_tool(self):
        """Test converting to OpenAI tool format."""
        openai_tool = self.tool.to_openai_tool()

        assert openai_tool["type"] == "function"
        assert openai_tool["function"]["name"] == "test_tool"
        assert (
            "description" in openai_tool["function"]
            and openai_tool["function"]["description"] == "A test tool"
        )

    def test_to_mcp_tool(self):
        """Test converting to MCP tool format."""
        mcp_tool = self.tool.to_mcp_tool()

        assert mcp_tool["name"] == "test_tool"
        assert mcp_tool["description"] == "A test tool"
        assert "inputSchema" in mcp_tool


class TestMCPToolRegistry:
    """Test MCPToolRegistry functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = MCPToolRegistry()

    def test_empty_registry(self):
        """Test empty registry state."""
        assert len(self.registry.clients) == 0
        assert len(self.registry.tools) == 0
        assert len(self.registry.get_all_tools()) == 0

    def test_add_client(self):
        """Test adding a client to the registry."""
        mock_client = MagicMock()

        # Mock tool map with two tools
        mock_tool1 = MagicMock()
        mock_tool1.name = "tool1"
        mock_tool1.description = "Tool 1"
        mock_tool1.inputSchema = {}

        mock_tool2 = MagicMock()
        mock_tool2.name = "tool2"
        mock_tool2.description = "Tool 2"
        mock_tool2.inputSchema = {}

        mock_client.tool_map = {"tool1": mock_tool1, "tool2": mock_tool2}

        self.registry.add_client("test_server", mock_client)

        assert "test_server" in self.registry.clients
        assert self.registry.clients["test_server"] == mock_client

        # Should have created tools with prefixed names
        assert "test_server:tool1" in self.registry.tools
        assert "test_server:tool2" in self.registry.tools

    def test_get_all_tools(self):
        """Test getting all tools from registry."""
        mock_client = MagicMock()

        # Mock tool map
        mock_tool1 = MagicMock()
        mock_tool1.name = "tool1"
        mock_tool1.description = "Tool 1"
        mock_tool1.inputSchema = {}

        mock_tool2 = MagicMock()
        mock_tool2.name = "tool2"
        mock_tool2.description = "Tool 2"
        mock_tool2.inputSchema = {}

        mock_client.tool_map = {"tool1": mock_tool1, "tool2": mock_tool2}

        self.registry.add_client("test_server", mock_client)

        tools = self.registry.get_all_tools()
        assert len(tools) == 2

        tool_names = [tool.name for tool in tools]
        assert "tool1" in tool_names
        assert "tool2" in tool_names

    def test_get_tools_for_client(self):
        """Test getting tools for a specific client."""
        mock_client1 = MagicMock()
        mock_client2 = MagicMock()

        # Mock tool maps
        mock_tool1 = MagicMock()
        mock_tool1.name = "tool1"
        mock_tool1.description = "Tool 1"
        mock_tool1.inputSchema = {}

        mock_tool2 = MagicMock()
        mock_tool2.name = "tool2"
        mock_tool2.description = "Tool 2"
        mock_tool2.inputSchema = {}

        mock_client1.tool_map = {"tool1": mock_tool1}
        mock_client2.tool_map = {"tool2": mock_tool2}

        self.registry.add_client("server1", mock_client1)
        self.registry.add_client("server2", mock_client2)

        server1_tools = self.registry.get_tools_for_client("server1")
        server2_tools = self.registry.get_tools_for_client("server2")

        assert len(server1_tools) == 1
        assert len(server2_tools) == 1
        assert server1_tools[0].name == "tool1"
        assert server2_tools[0].name == "tool2"

    def test_get_tool(self):
        """Test getting a specific tool by name."""
        mock_client = MagicMock()

        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.description = "Test Tool"
        mock_tool.inputSchema = {}

        mock_client.tool_map = {"test_tool": mock_tool}

        self.registry.add_client("test_server", mock_client)

        # Get tool by full name
        tool = self.registry.get_tool("test_server:test_tool")
        assert tool is not None
        assert tool.name == "test_tool"

        # Non-existent tool should return None
        non_existent = self.registry.get_tool("non_existent")
        assert non_existent is None
