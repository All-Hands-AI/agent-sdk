"""Tests to verify that Agent.init_state modifies state in-place."""

import tempfile
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import SecretStr

from openhands.sdk.agent.agent import Agent
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.event import SystemPromptEvent
from openhands.sdk.llm import LLM
from openhands.sdk.tool import Tool
from openhands.sdk.workspace import LocalWorkspace


class TestAgentInitStateInPlace:
    """Tests for Agent.init_state in-place state modification."""

    def setup_method(self):
        """Set up test environment."""
        self.llm = LLM(
            model="gpt-4o", api_key=SecretStr("test-key"), service_id="test-llm"
        )

    def test_init_state_modifies_state_in_place(self):
        """Test that init_state modifies the ConversationState object in-place."""
        with tempfile.TemporaryDirectory() as temp_dir:
            agent = Agent(llm=self.llm, tools=[])
            state = ConversationState.create(
                id=uuid4(),
                agent=agent,
                workspace=LocalWorkspace(working_dir=temp_dir),
                persistence_dir=None,
            )

            # Capture the object id before init_state
            state_id_before = id(state)

            # Track if on_event was called
            events_added = []

            def on_event(event):
                events_added.append(event)

            # Call init_state
            agent.init_state(state, on_event=on_event)

            # Verify the state object is the same (modified in-place)
            state_id_after = id(state)
            assert (
                state_id_before == state_id_after
            ), "init_state should modify state in-place, not create a new object"

            # Verify that a SystemPromptEvent was added
            assert len(events_added) == 1, "SystemPromptEvent should be added"
            assert isinstance(
                events_added[0], SystemPromptEvent
            ), "The event should be a SystemPromptEvent"

    def test_init_state_configures_bash_tool_env_provider(self):
        """Test that init_state configures bash tool with env_provider and env_masker when available."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Try to create agent with bash tool - skip test if tool not available
            try:
                from openhands.sdk.tool.registry import tool_exists

                if not tool_exists("execute_bash"):
                    pytest.skip("execute_bash tool not available in test environment")
            except ImportError:
                pytest.skip("Tool registry not available")

            agent = Agent(llm=self.llm, tools=[Tool(name="execute_bash")])
            state = ConversationState.create(
                id=uuid4(),
                agent=agent,
                workspace=LocalWorkspace(working_dir=temp_dir),
                persistence_dir=None,
            )

            # Mock the secrets manager
            mock_secrets_manager = MagicMock()
            mock_secrets_manager.get_secrets_as_env_vars.return_value = {"KEY": "value"}
            mock_secrets_manager.mask_secrets_in_output.return_value = "masked"
            state._secrets_manager = mock_secrets_manager

            def on_event(event):
                state.events.append(event)

            # Call init_state
            agent.init_state(state, on_event=on_event)

            # Verify that the bash tool was configured
            bash_tool = agent.tools_map.get("execute_bash")
            assert bash_tool is not None, "execute_bash tool should exist"

            # Get the executable tool and check if env_provider was set
            try:
                executable_tool = bash_tool.as_executable()
                assert hasattr(
                    executable_tool.executor, "env_provider"
                ), "Bash executor should have env_provider set"
                assert hasattr(
                    executable_tool.executor, "env_masker"
                ), "Bash executor should have env_masker set"

                # Test the env_provider works
                env_vars = executable_tool.executor.env_provider("test_cmd")
                assert env_vars == {"KEY": "value"}

                # Test the env_masker works
                masked = executable_tool.executor.env_masker("test output")
                assert masked == "masked"
            except NotImplementedError:
                # Tool has no executor, skip validation
                pass

    def test_init_state_adds_system_prompt_only_when_no_events(self):
        """Test that SystemPromptEvent is only added when there are no LLM convertible messages."""
        with tempfile.TemporaryDirectory() as temp_dir:
            agent = Agent(llm=self.llm, tools=[])
            state = ConversationState.create(
                id=uuid4(),
                agent=agent,
                workspace=LocalWorkspace(working_dir=temp_dir),
                persistence_dir=None,
            )

            events_added = []

            def on_event(event):
                events_added.append(event)
                # Also add to state.events so subsequent calls can detect it
                state.events.append(event)

            # First init_state call - should add SystemPromptEvent
            agent.init_state(state, on_event=on_event)
            assert len(events_added) == 1
            assert isinstance(events_added[0], SystemPromptEvent)

            # Create a new agent with same config
            agent2 = Agent(llm=self.llm, tools=[])

            # Clear the tracking list but not state.events
            events_added.clear()

            # Second init_state call on state that already has events
            # should NOT add another SystemPromptEvent
            agent2.init_state(state, on_event=on_event)
            assert (
                len(events_added) == 0
            ), "SystemPromptEvent should not be added when events already exist"

    def test_init_state_preserves_state_attributes(self):
        """Test that init_state preserves state attributes like agent_status."""
        from openhands.sdk.conversation.state import AgentExecutionStatus

        with tempfile.TemporaryDirectory() as temp_dir:
            agent = Agent(llm=self.llm, tools=[])
            state = ConversationState.create(
                id=uuid4(),
                agent=agent,
                workspace=LocalWorkspace(working_dir=temp_dir),
                persistence_dir=None,
            )

            # Set some state attributes
            original_status = state.agent_status
            original_max_iterations = state.max_iterations

            def on_event(event):
                pass

            # Call init_state
            agent.init_state(state, on_event=on_event)

            # Verify state attributes are preserved
            assert (
                state.agent_status == original_status
            ), "agent_status should be preserved"
            assert (
                state.max_iterations == original_max_iterations
            ), "max_iterations should be preserved"

    def test_init_state_multiple_calls_are_idempotent(self):
        """Test that calling init_state multiple times doesn't cause issues."""
        with tempfile.TemporaryDirectory() as temp_dir:
            agent = Agent(llm=self.llm, tools=[])
            state = ConversationState.create(
                id=uuid4(),
                agent=agent,
                workspace=LocalWorkspace(working_dir=temp_dir),
                persistence_dir=None,
            )

            events_added = []

            def on_event(event):
                events_added.append(event)
                # Add to state.events so second call can see them
                state.events.append(event)

            # First call
            agent.init_state(state, on_event=on_event)
            first_call_events = len(events_added)
            assert first_call_events == 1, "First call should add SystemPromptEvent"

            # Second call - agent already initialized
            agent.init_state(state, on_event=on_event)
            second_call_events = len(events_added) - first_call_events

            # Second call should not add more events (since events already exist)
            assert second_call_events == 0, "Second init_state call should not add events"
