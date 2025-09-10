"""Test agent serialization with DiscriminatedUnionMixin."""

from typing import Annotated

from pydantic import BaseModel

from openhands.sdk.agent import Agent, AgentType
from openhands.sdk.llm import LLM
from openhands.sdk.utils.discriminated_union import DiscriminatedUnionType


def test_agent_supports_polymorphic_deserialization() -> None:
    """Test that Agent supports polymorphic deserialization from dict data."""
    # Create a simple LLM instance
    llm = LLM(model="test-model")

    # Create a simple agent instance
    agent_data = {
        "llm": llm.model_dump(),
        "kind": "Agent",  # Use base Agent class
    }

    # Deserialize using the base class
    deserialized_agent = Agent.model_validate(agent_data)

    # Should deserialize to the correct type
    assert isinstance(deserialized_agent, Agent)
    assert deserialized_agent.llm.model == "test-model"


def test_agent_supports_polymorphic_field_deserialization() -> None:
    """Test that Agent supports polymorphic deserialization when used as a field."""

    class AgentContainer(BaseModel):
        agent: Annotated[Agent, DiscriminatedUnionType[Agent]]

    # Create a simple agent directly
    llm = LLM(model="test-model")
    agent = Agent(llm=llm)
    container = AgentContainer(agent=agent)

    # Test that the agent was created correctly
    assert isinstance(container.agent, Agent)
    assert container.agent.llm.model == "test-model"


def test_agent_supports_nested_polymorphic_deserialization() -> None:
    """Test that Agent supports polymorphic deserialization when nested in lists."""

    class AgentRegistry(BaseModel):
        agents: list[Annotated[Agent, DiscriminatedUnionType[Agent]]]

    # Create simple agents directly
    llm1 = LLM(model="test-model-1")
    llm2 = LLM(model="test-model-2")
    agents = [Agent(llm=llm1), Agent(llm=llm2)]
    registry = AgentRegistry(agents=agents)

    # Test that the agents were created correctly
    assert len(registry.agents) == 2
    assert isinstance(registry.agents[0], Agent)
    assert isinstance(registry.agents[1], Agent)
    assert registry.agents[0].llm.model == "test-model-1"
    assert registry.agents[1].llm.model == "test-model-2"


def test_agent_model_validate_dict() -> None:
    """Test Agent model_validate with dictionary input."""
    llm = LLM(model="test-model")
    agent_data = {
        "llm": llm.model_dump(),
        "kind": "Agent",
    }

    # Test with valid kind
    result = Agent.model_validate(agent_data)
    assert isinstance(result, Agent)
    assert result.llm.model == "test-model"


def test_agent_fallback_behavior() -> None:
    """Test fallback behavior when discriminated union logic doesn't apply."""

    # Create agent data without kind
    llm = LLM(model="test-model")
    no_kind_data = {
        "llm": llm.model_dump(),
    }

    # Test with missing kind - should fallback to base class
    result = Agent.model_validate(no_kind_data)
    assert isinstance(result, Agent)
    assert result.llm.model == "test-model"

    # Test with invalid kind - should fallback to base class
    invalid_kind_data = {**no_kind_data, "kind": "InvalidAgent"}
    result = Agent.model_validate(invalid_kind_data)
    assert isinstance(result, Agent)
    assert result.llm.model == "test-model"


def test_agent_preserves_pydantic_parameters() -> None:
    """Test that all Pydantic validation parameters are preserved."""
    llm = LLM(model="test-model")
    agent_data = {
        "llm": llm.model_dump(),
        "kind": "Agent",
    }

    # Test with strict mode
    result = Agent.model_validate(agent_data, strict=True)
    assert isinstance(result, Agent)

    # Test with context
    context = {"test": "value"}
    result = Agent.model_validate(agent_data, context=context)
    assert isinstance(result, Agent)


def test_agent_type_annotation_works() -> None:
    """Test that AgentType annotation works correctly."""

    class AgentWrapper(BaseModel):
        agent: AgentType

    llm = LLM(model="test-model")
    agent = Agent(llm=llm)
    wrapper = AgentWrapper(agent=agent)

    # Test that the agent was created correctly
    assert isinstance(wrapper.agent, Agent)
    assert wrapper.agent.llm.model == "test-model"
