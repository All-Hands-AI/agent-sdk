"""Tests for Agent immutability and statelessness."""

import pytest
from pydantic import SecretStr, ValidationError

from openhands.sdk.agent.agent.agent import Agent
from openhands.sdk.llm import LLM


class TestAgentImmutability:
    """Test Agent immutability and statelessness."""

    def setup_method(self):
        """Set up test environment."""
        self.llm = LLM(model="gpt-4", api_key=SecretStr("test-key"))

    def test_agent_is_frozen(self):
        """Test that Agent instances are frozen (immutable)."""
        agent = Agent(llm=self.llm, tools=[])

        # Test that we cannot modify any field
        with pytest.raises(ValidationError, match="Instance is frozen"):
            agent.llm = "new_value"  # type: ignore[assignment]

        with pytest.raises(ValidationError, match="Instance is frozen"):
            agent.agent_context = None

        with pytest.raises(ValidationError, match="Instance is frozen"):
            agent.system_prompt_filename = "new_prompt.j2"

        with pytest.raises(ValidationError, match="Instance is frozen"):
            agent.condenser_instance = None

        with pytest.raises(ValidationError, match="Instance is frozen"):
            agent.cli_mode = False

    def test_system_message_is_computed_property(self):
        """Test that system_message is computed on-demand, not stored."""
        agent = Agent(llm=self.llm, tools=[])

        # Get system message multiple times
        msg1 = agent.system_message
        msg2 = agent.system_message

        # Should be the same content
        assert msg1 == msg2
        assert isinstance(msg1, str)
        assert len(msg1) > 0

        # Verify it's not stored as an instance variable
        assert not hasattr(agent, "_system_message")
        assert "system_message" not in agent.__dict__

    def test_agent_with_different_configs_are_different(self):
        """Test that agents with different configs produce different system messages."""
        agent1 = Agent(llm=self.llm, tools=[], cli_mode=True)
        agent2 = Agent(llm=self.llm, tools=[], cli_mode=False)

        # System messages should be different due to cli_mode
        msg1 = agent1.system_message
        msg2 = agent2.system_message

        # They should be different (cli_mode affects the template)
        assert msg1 != msg2

    def test_condenser_property_access(self):
        """Test that condenser property works correctly."""
        # Test with None condenser
        agent1 = Agent(llm=self.llm, tools=[], condenser=None)
        assert agent1.condenser is None

        # For testing with a condenser, we'll just test that the property works
        # We don't need to test with a real condenser since that would require
        # importing and setting up the actual Condenser class

    def test_agent_properties_are_accessible(self):
        """Test that all Agent properties are accessible and return expected types."""
        agent = Agent(llm=self.llm, tools=[])

        # Test inherited properties from AgentBase
        assert agent.llm == self.llm
        from types import MappingProxyType

        assert isinstance(agent.tools, MappingProxyType)  # Should be MappingProxyType
        assert agent.agent_context is None
        assert agent.name == "Agent"
        assert isinstance(agent.prompt_dir, str)

        # Test Agent-specific properties
        assert isinstance(agent.system_message, str)
        assert agent.condenser is None
        assert agent.system_prompt_filename == "system_prompt.j2"
        assert agent.cli_mode is True

    def test_agent_is_truly_stateless(self):
        """Test that Agent doesn't store computed state."""
        agent = Agent(llm=self.llm, tools=[])

        # Access system_message multiple times
        for _ in range(3):
            msg = agent.system_message
            assert isinstance(msg, str)
            assert len(msg) > 0

        # Verify no computed state is stored
        # The only fields should be the ones we explicitly defined
        expected_fields = {
            "llm",
            "agent_context",
            "tools_map",
            "system_prompt_filename",
            "condenser_instance",
            "cli_mode",
        }

        # Get all fields from the model class (not instance)
        actual_fields = set(Agent.model_fields.keys())
        assert actual_fields == expected_fields

        # Verify no additional attributes are stored
        assert not hasattr(agent, "_system_message")
        assert not hasattr(agent, "_computed_system_message")

    def test_multiple_agents_are_independent(self):
        """Test that multiple Agent instances are independent."""
        agent1 = Agent(
            llm=self.llm, tools=[], system_prompt_filename="system_prompt.j2"
        )
        agent2 = Agent(
            llm=self.llm, tools=[], system_prompt_filename="system_prompt.j2"
        )

        # They should have the same configuration
        assert agent1.system_prompt_filename == agent2.system_prompt_filename
        assert agent1.cli_mode == agent2.cli_mode

        # But they should be different instances
        assert agent1 is not agent2

        # And their system messages should be identical (same config)
        assert agent1.system_message == agent2.system_message
