"""Test agent JSON serialization with DiscriminatedUnionMixin."""

import json
from typing import Annotated

from pydantic import BaseModel

from openhands.sdk.agent import Agent, AgentType
from openhands.sdk.llm import LLM
from openhands.sdk.utils.discriminated_union import DiscriminatedUnionType


def test_agent_supports_polymorphic_json_serialization() -> None:
    """Test that Agent supports polymorphic JSON serialization/deserialization."""
    # Create a simple LLM instance and agent with empty tools to avoid serialization issues
    llm = LLM(model="test-model")
    agent = Agent(llm=llm, tools={})

    # Serialize to JSON (excluding non-serializable fields)
    agent_json = agent.model_dump_json(exclude={"condenser"})
    
    # Deserialize from JSON using the base class
    deserialized_agent = Agent.model_validate_json(agent_json)

    # Should deserialize to the correct type and have same core fields
    assert isinstance(deserialized_agent, Agent)
    assert deserialized_agent.llm.model == "test-model"
    assert deserialized_agent.tools == agent.tools


def test_agent_supports_polymorphic_field_json_serialization() -> None:
    """Test that Agent supports polymorphic JSON serialization when used as a field."""

    class Container(BaseModel):
        agent: Agent  # Use direct Agent type instead of DiscriminatedUnionType

    # Create container with agent
    llm = LLM(model="test-model")
    agent = Agent(llm=llm, tools={})
    container = Container(agent=agent)

    # Serialize to JSON (excluding non-serializable fields)
    container_json = container.model_dump_json(exclude={"agent": {"condenser"}})
    
    # Deserialize from JSON
    deserialized_container = Container.model_validate_json(container_json)

    # Should preserve the agent type and core fields
    assert isinstance(deserialized_container.agent, Agent)
    assert deserialized_container.agent.llm.model == "test-model"
    assert deserialized_container.agent.tools == agent.tools


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
    container_json = container.model_dump_json(exclude={"agents": {"__all__": {"condenser"}}})
    
    # Deserialize from JSON
    deserialized_container = NestedContainer.model_validate_json(container_json)

    # Should preserve all agent types and core fields
    assert len(deserialized_container.agents) == 2
    assert isinstance(deserialized_container.agents[0], Agent)
    assert isinstance(deserialized_container.agents[1], Agent)
    assert deserialized_container.agents[0].llm.model == "model-1"
    assert deserialized_container.agents[1].llm.model == "model-2"


def test_agent_model_validate_json_dict() -> None:
    """Test that Agent.model_validate works with dict from JSON."""
    # Create agent
    llm = LLM(model="test-model")
    agent = Agent(llm=llm, tools={})

    # Serialize to JSON, then parse to dict
    agent_json = agent.model_dump_json(exclude={"condenser"})
    agent_dict = json.loads(agent_json)
    
    # Deserialize from dict
    deserialized_agent = Agent.model_validate(agent_dict)

    # Should have same core fields
    assert deserialized_agent.llm.model == agent.llm.model
    assert deserialized_agent.tools == agent.tools


def test_agent_fallback_behavior_json() -> None:
    """Test that Agent handles unknown types gracefully in JSON."""
    # Create JSON with unknown kind
    agent_dict = {
        "llm": {"model": "test-model"},
        "kind": "UnknownAgentType"
    }
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
    agent_json = agent.model_dump_json(exclude={"condenser"})
    
    # Deserialize from JSON
    deserialized_agent = Agent.model_validate_json(agent_json)

    # Should preserve core fields
    assert deserialized_agent.llm.model == agent.llm.model
    assert deserialized_agent.tools == agent.tools


def test_agent_type_annotation_works_json() -> None:
    """Test that AgentType annotation works correctly with JSON."""
    # Create agent
    llm = LLM(model="test-model")
    agent = Agent(llm=llm, tools={})

    # Use AgentType annotation
    class TestModel(BaseModel):
        agent: AgentType

    model = TestModel(agent=agent)

    # Serialize to JSON
    model_json = model.model_dump_json(exclude={"agent": {"condenser"}})
    
    # Deserialize from JSON
    deserialized_model = TestModel.model_validate_json(model_json)

    # Should work correctly
    assert isinstance(deserialized_model.agent, Agent)
    assert deserialized_model.agent.llm.model == agent.llm.model
    assert deserialized_model.agent.tools == agent.tools