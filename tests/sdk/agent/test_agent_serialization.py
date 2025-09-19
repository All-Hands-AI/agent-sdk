"""Test agent JSON serialization with DiscriminatedUnionMixin."""

import json
from unittest.mock import Mock

import mcp.types
from pydantic import BaseModel

from openhands.sdk.agent import Agent
from openhands.sdk.agent.base import AgentBase
from openhands.sdk.llm import LLM
from openhands.sdk.mcp.client import MCPClient
from openhands.sdk.mcp.tool import MCPTool
from openhands.sdk.tool.tool import ToolBase


def create_mock_mcp_tool(name: str = "test_tool") -> MCPTool:
    # Create mock MCP tool and client
    mock_mcp_tool = mcp.types.Tool(
        name=name,
        description=f"A test MCP tool named {name}",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query parameter"}
            },
            "required": ["query"],
        },
    )
    mock_client = Mock(spec=MCPClient)
    mcp_tool = MCPTool.create(mock_mcp_tool, mock_client)
    return mcp_tool


def test_agent_supports_polymorphic_json_serialization() -> None:
    """Test that Agent supports polymorphic JSON serialization/deserialization."""
    # Create a simple LLM instance and agent with empty tools
    llm = LLM(model="test-model")
    agent = Agent(llm=llm, tools={})

    # Serialize to JSON (excluding non-serializable fields)
    agent_json = agent.model_dump_json()

    # Deserialize from JSON using the base class
    deserialized_agent = Agent.model_validate_json(agent_json)

    # Should deserialize to the correct type and have same core fields
    assert isinstance(deserialized_agent, Agent)
    assert deserialized_agent.model_dump() == agent.model_dump()


def test_mcp_tool_serialization():
    tool = create_mock_mcp_tool()
    dumped = tool.model_dump_json()
    loaded = ToolBase.model_validate_json(dumped)
    assert loaded.model_dump_json() == dumped


def test_agent_serialization_should_include_mcp_tool() -> None:
    # Create a simple LLM instance and agent with empty tools
    llm = LLM(model="test-model")
    agent = Agent(llm=llm, tools={"test_tool": create_mock_mcp_tool()})

    # Serialize to JSON (excluding non-serializable fields)
    agent_dump = agent.model_dump()
    assert "tools" in agent_dump and isinstance(agent_dump["tools"], dict)
    assert "test_tool" in agent_dump["tools"]
    assert "mcp_tool" in agent_dump["tools"]["test_tool"]
    agent_json = agent.model_dump_json()

    # Deserialize from JSON using the base class
    deserialized_agent = Agent.model_validate_json(agent_json)

    # Should deserialize to the correct type and have same core fields
    assert isinstance(deserialized_agent, Agent)
    assert deserialized_agent.model_dump_json() == agent.model_dump_json()


def test_agent_supports_polymorphic_field_json_serialization() -> None:
    """Test that Agent supports polymorphic JSON serialization when used as a field."""

    class Container(BaseModel):
        agent: Agent  # Use direct Agent type instead of DiscriminatedUnionType

    # Create container with agent
    llm = LLM(model="test-model")
    agent = Agent(llm=llm, tools={})
    container = Container(agent=agent)

    # Serialize to JSON (excluding non-serializable fields)
    container_json = container.model_dump_json()

    # Deserialize from JSON
    deserialized_container = Container.model_validate_json(container_json)

    # Should preserve the agent type and core fields
    assert isinstance(deserialized_container.agent, Agent)
    assert deserialized_container.agent.model_dump() == agent.model_dump()


def test_agent_supports_nested_polymorphic_json_serialization() -> None:
    """Test that Agent supports nested polymorphic JSON serialization."""

    class NestedContainer(BaseModel):
        agents: list[Agent]  # Use direct Agent type

    # Create container with multiple agents
    llm1 = LLM(model="model-1")
    llm2 = LLM(model="model-2")
    agent1 = Agent(llm=llm1, tools={})
    agent2 = Agent(llm=llm2, tools={})
    container = NestedContainer(agents=[agent1, agent2])

    # Serialize to JSON (excluding non-serializable fields)
    container_json = container.model_dump_json()

    # Deserialize from JSON
    deserialized_container = NestedContainer.model_validate_json(container_json)

    # Should preserve all agent types and core fields
    assert len(deserialized_container.agents) == 2
    assert isinstance(deserialized_container.agents[0], Agent)
    assert isinstance(deserialized_container.agents[1], Agent)
    assert deserialized_container.agents[0].model_dump() == agent1.model_dump()
    assert deserialized_container.agents[1].model_dump() == agent2.model_dump()


def test_agent_model_validate_json_dict() -> None:
    """Test that Agent.model_validate works with dict from JSON."""
    # Create agent
    llm = LLM(model="test-model")
    agent = Agent(llm=llm, tools={})

    # Serialize to JSON, then parse to dict
    agent_json = agent.model_dump_json()
    agent_dict = json.loads(agent_json)

    # Deserialize from dict
    deserialized_agent = Agent.model_validate(agent_dict)

    assert deserialized_agent.model_dump() == agent.model_dump()


def test_agent_fallback_behavior_json() -> None:
    """Test that Agent handles unknown types gracefully in JSON."""
    # Create JSON with unknown kind
    agent_dict = {"llm": {"model": "test-model"}, "kind": "UnknownAgentType"}
    agent_json = json.dumps(agent_dict)

    # Should fall back to base Agent type
    deserialized_agent = Agent.model_validate_json(agent_json)
    assert isinstance(deserialized_agent, Agent)
    assert deserialized_agent.llm.model == "test-model"


def test_agent_preserves_pydantic_parameters_json() -> None:
    """Test that Agent preserves Pydantic parameters through JSON serialization."""
    # Create agent with extra data
    llm = LLM(model="test-model")
    agent = Agent(llm=llm, tools={})

    # Serialize to JSON
    agent_json = agent.model_dump_json()

    # Deserialize from JSON
    deserialized_agent = Agent.model_validate_json(agent_json)

    assert deserialized_agent.model_dump() == agent.model_dump()


def test_agent_type_annotation_works_json() -> None:
    """Test that AgentType annotation works correctly with JSON."""
    # Create agent
    llm = LLM(model="test-model")
    agent = Agent(llm=llm, tools={})

    # Use AgentType annotation
    class TestModel(BaseModel):
        agent: AgentBase

    model = TestModel(agent=agent)

    # Serialize to JSON
    model_json = model.model_dump_json()

    # Deserialize from JSON
    deserialized_model = TestModel.model_validate_json(model_json)

    # Should work correctly
    assert isinstance(deserialized_model.agent, Agent)
    assert deserialized_model.agent.model_dump() == agent.model_dump()
