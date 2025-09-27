"""Test LLM reconciliation logic in agent deserialization."""

import tempfile
import uuid

import pytest
from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.agent.base import AgentBase
from openhands.sdk.context.condenser.llm_summarizing_condenser import (
    LLMSummarizingCondenser,
)
from openhands.sdk.conversation import Conversation
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.conversation.types import ConversationCallbackType
from openhands.sdk.event.llm_convertible import SystemPromptEvent
from openhands.sdk.io import InMemoryFileStore
from openhands.sdk.llm import LLM, TextContent
from openhands.sdk.tool import ToolSpec


class DummyAgent(AgentBase):
    """A simple dummy agent for testing."""

    def __init__(self, **kwargs):
        # Set default LLM if not provided
        if "llm" not in kwargs:
            kwargs["llm"] = LLM(
                model="gpt-4o-mini",
                api_key=SecretStr("test-key"),
                service_id="test-llm",
            )
        if "tools" not in kwargs:
            kwargs["tools"] = []
        # Remove 'kind' if present (used for polymorphic deserialization)
        kwargs.pop("kind", None)
        super().__init__(**kwargs)

    def init_state(
        self, state: ConversationState, on_event: ConversationCallbackType
    ) -> None:
        event = SystemPromptEvent(
            source="agent", system_prompt=TextContent(text="dummy"), tools=[]
        )
        on_event(event)

    def step(
        self, state: ConversationState, on_event: ConversationCallbackType
    ) -> None:
        pass


def test_resolve_diff_with_condenser_llm():
    """Test resolve_diff_from_deserialized handles nested LLMs in condenser."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create original agent with condenser containing LLM
        main_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("main-key"), service_id="main-llm"
        )
        condenser_llm = LLM(
            model="gpt-3.5-turbo",
            api_key=SecretStr("condenser-key"),
            service_id="condenser-llm",
        )
        condenser = LLMSummarizingCondenser(
            llm=condenser_llm, max_size=80, keep_first=10
        )
        tools = [ToolSpec(name="BashTool", params={"working_dir": temp_dir})]

        original_agent = Agent(llm=main_llm, tools=tools, condenser=condenser)

        # Serialize and deserialize to simulate persistence
        # This will mask the api_keys in both main LLM and condenser LLM
        serialized = original_agent.model_dump_json()
        deserialized_agent = AgentBase.model_validate_json(serialized)

        # Verify that deserialized agent has masked secrets
        assert deserialized_agent.llm.api_key is not None
        assert deserialized_agent.llm.api_key.get_secret_value() == "**********"
        # Type assertion to help with type checking
        assert isinstance(deserialized_agent.condenser, LLMSummarizingCondenser)
        assert deserialized_agent.condenser.llm.api_key is not None
        assert (
            deserialized_agent.condenser.llm.api_key.get_secret_value() == "**********"
        )

        # Create runtime agent with same configuration but real secrets
        runtime_main_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("main-key"), service_id="main-llm"
        )
        runtime_condenser_llm = LLM(
            model="gpt-3.5-turbo",
            api_key=SecretStr("condenser-key"),
            service_id="condenser-llm",
        )
        runtime_condenser = LLMSummarizingCondenser(
            llm=runtime_condenser_llm, max_size=80, keep_first=10
        )
        runtime_agent = Agent(
            llm=runtime_main_llm, tools=tools, condenser=runtime_condenser
        )

        # Should resolve successfully - this is the main test
        resolved = runtime_agent.resolve_diff_from_deserialized(deserialized_agent)

        # Verify that resolved agent has the runtime secrets
        assert resolved.llm.api_key is not None
        assert resolved.llm.api_key.get_secret_value() == "main-key"
        # Type assertion to help with type checking
        assert isinstance(resolved.condenser, LLMSummarizingCondenser)
        assert resolved.condenser.llm.api_key is not None
        assert resolved.condenser.llm.api_key.get_secret_value() == "condenser-key"

        # Verify other fields are preserved
        assert resolved.llm.model == runtime_agent.llm.model
        assert isinstance(resolved.condenser, LLMSummarizingCondenser)
        assert isinstance(runtime_agent.condenser, LLMSummarizingCondenser)
        assert resolved.condenser.llm.model == runtime_agent.condenser.llm.model
        assert resolved.condenser.max_size == runtime_agent.condenser.max_size
        assert resolved.condenser.keep_first == runtime_agent.condenser.keep_first
        assert resolved.__class__ == runtime_agent.__class__

        # Test model_dump equality (excluding secrets which are now reconciled)
        assert resolved.model_dump(exclude_none=True) == runtime_agent.model_dump(
            exclude_none=True
        )


def test_resolve_diff_with_multiple_nested_llms():
    """Test resolve_diff_from_deserialized handles multiple nested LLMs."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create original agent with multiple condensers
        main_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("main-key"), service_id="main-llm"
        )
        condenser_llm = LLM(
            model="gpt-3.5-turbo",
            api_key=SecretStr("condenser-key"),
            service_id="condenser-llm",
        )

        condenser = LLMSummarizingCondenser(
            llm=condenser_llm, max_size=80, keep_first=10
        )
        tools = [ToolSpec(name="BashTool", params={"working_dir": temp_dir})]

        original_agent = Agent(
            llm=main_llm,
            tools=tools,
            condenser=condenser,
        )

        # Serialize and deserialize to simulate persistence
        serialized = original_agent.model_dump_json()
        deserialized_agent = AgentBase.model_validate_json(serialized)

        # Verify that all LLMs have masked secrets
        assert deserialized_agent.llm.api_key is not None
        assert deserialized_agent.llm.api_key.get_secret_value() == "**********"
        assert isinstance(deserialized_agent.condenser, LLMSummarizingCondenser)
        assert deserialized_agent.condenser.llm.api_key is not None
        assert (
            deserialized_agent.condenser.llm.api_key.get_secret_value() == "**********"
        )

        # Create runtime agent with same configuration but real secrets
        runtime_main_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("main-key"), service_id="main-llm"
        )
        runtime_condenser_llm = LLM(
            model="gpt-3.5-turbo",
            api_key=SecretStr("condenser-key"),
            service_id="condenser-llm",
        )

        runtime_condenser = LLMSummarizingCondenser(
            llm=runtime_condenser_llm, max_size=80, keep_first=10
        )
        runtime_agent = Agent(
            llm=runtime_main_llm,
            tools=tools,
            condenser=runtime_condenser,
        )

        # Should resolve successfully
        resolved = runtime_agent.resolve_diff_from_deserialized(deserialized_agent)

        # Verify that all resolved LLMs have the runtime secrets
        assert resolved.llm.api_key is not None
        assert resolved.llm.api_key.get_secret_value() == "main-key"
        assert isinstance(resolved.condenser, LLMSummarizingCondenser)
        assert resolved.condenser.llm.api_key is not None
        assert resolved.condenser.llm.api_key.get_secret_value() == "condenser-key"

        # Verify all models are preserved
        assert resolved.llm.model == "gpt-4o-mini"
        assert resolved.condenser.llm.model == "gpt-3.5-turbo"

        # Test model_dump equality
        assert resolved.model_dump(exclude_none=True) == runtime_agent.model_dump(
            exclude_none=True
        )


def test_resolve_diff_llm_count_mismatch():
    """Test resolve_diff_from_deserialized raises error when LLM counts differ."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create original agent with condenser
        main_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("main-key"), service_id="main-llm"
        )
        condenser_llm = LLM(
            model="gpt-3.5-turbo",
            api_key=SecretStr("condenser-key"),
            service_id="condenser-llm",
        )
        condenser = LLMSummarizingCondenser(
            llm=condenser_llm, max_size=80, keep_first=10
        )
        tools = [ToolSpec(name="BashTool", params={"working_dir": temp_dir})]

        original_agent = Agent(llm=main_llm, tools=tools, condenser=condenser)

        # Serialize and deserialize
        serialized = original_agent.model_dump_json()
        deserialized_agent = AgentBase.model_validate_json(serialized)

        # Create runtime agent WITHOUT condenser (different LLM count)
        runtime_main_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("main-key"), service_id="main-llm"
        )
        runtime_agent = Agent(llm=runtime_main_llm, tools=tools)  # No condenser

        # Should raise error due to LLM count mismatch
        with pytest.raises(ValueError, match="Mismatch in number of LLMs"):
            runtime_agent.resolve_diff_from_deserialized(deserialized_agent)


def test_resolve_diff_service_id_mismatch():
    """Test resolve_diff_from_deserialized raises error when service_ids differ."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create original agent with condenser
        main_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("main-key"), service_id="main-llm"
        )
        condenser_llm = LLM(
            model="gpt-3.5-turbo",
            api_key=SecretStr("condenser-key"),
            service_id="condenser-llm",
        )
        condenser = LLMSummarizingCondenser(
            llm=condenser_llm, max_size=80, keep_first=10
        )
        tools = [ToolSpec(name="BashTool", params={"working_dir": temp_dir})]

        original_agent = Agent(llm=main_llm, tools=tools, condenser=condenser)

        # Serialize and deserialize
        serialized = original_agent.model_dump_json()
        deserialized_agent = AgentBase.model_validate_json(serialized)

        # Create runtime agent with different service_id for condenser LLM
        runtime_main_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("main-key"), service_id="main-llm"
        )
        runtime_condenser_llm = LLM(
            model="gpt-3.5-turbo",
            api_key=SecretStr("condenser-key"),
            service_id="different-service-id",  # Different service_id
        )
        runtime_condenser = LLMSummarizingCondenser(
            llm=runtime_condenser_llm, max_size=80, keep_first=10
        )
        runtime_agent = Agent(
            llm=runtime_main_llm, tools=tools, condenser=runtime_condenser
        )

        # Should raise error due to service_id mismatch
        with pytest.raises(ValueError, match="Mismatch in LLM service_ids"):
            runtime_agent.resolve_diff_from_deserialized(deserialized_agent)


def test_resolve_diff_no_nested_llms():
    """Test resolve_diff_from_deserialized works when there are no nested LLMs."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create simple agent with only main LLM
        main_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("main-key"), service_id="main-llm"
        )
        tools = [ToolSpec(name="BashTool", params={"working_dir": temp_dir})]

        original_agent = Agent(llm=main_llm, tools=tools)

        # Serialize and deserialize
        serialized = original_agent.model_dump_json()
        deserialized_agent = AgentBase.model_validate_json(serialized)

        # Create runtime agent with same configuration
        runtime_main_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("main-key"), service_id="main-llm"
        )
        runtime_agent = Agent(llm=runtime_main_llm, tools=tools)

        # Should resolve successfully
        resolved = runtime_agent.resolve_diff_from_deserialized(deserialized_agent)

        # Verify that resolved agent has the runtime secrets
        assert resolved.llm.api_key is not None
        assert resolved.llm.api_key.get_secret_value() == "main-key"
        assert resolved.llm.model == runtime_agent.llm.model
        assert resolved.__class__ == runtime_agent.__class__

        # Test model_dump equality
        assert resolved.model_dump(exclude_none=True) == runtime_agent.model_dump(
            exclude_none=True
        )


def test_get_all_llms_discovery():
    """Test that get_all_llms correctly discovers all nested LLMs."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create agent with nested LLM
        main_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("main-key"), service_id="main-llm"
        )
        condenser_llm = LLM(
            model="gpt-3.5-turbo",
            api_key=SecretStr("condenser-key"),
            service_id="condenser-llm",
        )

        condenser = LLMSummarizingCondenser(
            llm=condenser_llm, max_size=80, keep_first=10
        )
        tools = [ToolSpec(name="BashTool", params={"working_dir": temp_dir})]

        agent = Agent(
            llm=main_llm,
            tools=tools,
            condenser=condenser,
        )

        # Get all LLMs
        all_llms = list(agent.get_all_llms())

        # Should find both LLMs
        assert len(all_llms) == 2

        # Verify we found the right LLMs by their models
        models = {llm.model for llm in all_llms}
        expected_models = {"gpt-4o-mini", "gpt-3.5-turbo"}
        assert models == expected_models

        # Verify we found the right LLMs by their service_ids
        service_ids = {llm.service_id for llm in all_llms}
        expected_service_ids = {"main-llm", "condenser-llm"}
        assert service_ids == expected_service_ids


def test_original_issue_reproduction():
    """Test that reproduces the original issue from the GitHub issue."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create agent with condenser - this reproduces the original issue scenario
        main_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="main-llm"
        )
        condenser_llm = LLM(
            model="gpt-3.5-turbo",
            api_key=SecretStr("condenser-key"),
            service_id="condenser-llm",
        )
        condenser = LLMSummarizingCondenser(
            llm=condenser_llm, max_size=80, keep_first=10
        )
        tools = [ToolSpec(name="BashTool", params={"working_dir": temp_dir})]

        # Create agent that would be saved to disk
        saved_agent = Agent(llm=main_llm, tools=tools, condenser=condenser)

        # Simulate saving to disk (serialization masks secrets)
        serialized = saved_agent.model_dump_json()
        # Simulate loading from disk
        loaded_agent = AgentBase.model_validate_json(serialized)

        # Create new agent with same config but fresh secrets (runtime scenario)
        runtime_main_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="main-llm"
        )
        runtime_condenser_llm = LLM(
            model="gpt-3.5-turbo",
            api_key=SecretStr("condenser-key"),
            service_id="condenser-llm",
        )
        runtime_condenser = LLMSummarizingCondenser(
            llm=runtime_condenser_llm, max_size=80, keep_first=10
        )
        runtime_agent = Agent(
            llm=runtime_main_llm, tools=tools, condenser=runtime_condenser
        )

        # This should NOT raise the error from the original issue:
        # "The Agent provided is different from the one in persisted state.
        # Diff: condenser: llm: api_key: SecretStr('**********') -> SecretStr('**********')"  # noqa: E501
        resolved = runtime_agent.resolve_diff_from_deserialized(loaded_agent)

        # Verify the resolution worked correctly
        assert resolved.llm.api_key is not None
        assert resolved.llm.api_key.get_secret_value() == "test-key"
        assert isinstance(resolved.condenser, LLMSummarizingCondenser)
        assert resolved.condenser.llm.api_key is not None
        assert resolved.condenser.llm.api_key.get_secret_value() == "condenser-key"
        assert resolved.llm.model == "gpt-4o-mini"
        assert resolved.condenser.llm.model == "gpt-3.5-turbo"


def test_conversation_restart_with_nested_llms():
    """Test conversation restart with agent containing nested LLMs."""
    # Create a default agent with dummy LLM + models + keys
    main_llm = LLM(
        model="gpt-4o-mini", api_key=SecretStr("main-key"), service_id="main-llm"
    )
    condenser_llm = LLM(
        model="gpt-3.5-turbo",
        api_key=SecretStr("condenser-key"),
        service_id="condenser-llm",
    )
    condenser = LLMSummarizingCondenser(llm=condenser_llm, max_size=80, keep_first=10)

    # Use the standard Agent class to avoid polymorphic deserialization issues
    agent = Agent(llm=main_llm, condenser=condenser, tools=[])

    # Create a file store for the conversation
    file_store = InMemoryFileStore()
    conversation_id = uuid.uuid4()

    # Create a conversation with the default agent + file store
    conversation1 = Conversation(
        agent=agent,
        persist_filestore=file_store,
        conversation_id=conversation_id,
    )

    # Verify the conversation was created successfully
    assert conversation1.id == conversation_id
    assert conversation1.agent.llm.api_key is not None
    assert conversation1.agent.llm.api_key.get_secret_value() == "main-key"
    assert isinstance(conversation1.agent.condenser, LLMSummarizingCondenser)
    assert conversation1.agent.condenser.llm.api_key is not None
    assert (
        conversation1.agent.condenser.llm.api_key.get_secret_value() == "condenser-key"
    )

    # Simulate some conversation activity (this will persist the state)
    # The conversation automatically persists the base state during initialization

    # Now attempt to restart the conversation with the same agent and conversation_id
    # Create a new agent instance with the same configuration
    restart_main_llm = LLM(
        model="gpt-4o-mini", api_key=SecretStr("main-key"), service_id="main-llm"
    )
    restart_condenser_llm = LLM(
        model="gpt-3.5-turbo",
        api_key=SecretStr("condenser-key"),
        service_id="condenser-llm",
    )
    restart_condenser = LLMSummarizingCondenser(
        llm=restart_condenser_llm, max_size=80, keep_first=10
    )

    restart_agent = Agent(llm=restart_main_llm, condenser=restart_condenser, tools=[])

    # Attempt to restart the conversation - this should work without errors
    conversation2 = Conversation(
        agent=restart_agent,
        persist_filestore=file_store,
        conversation_id=conversation_id,  # Same conversation_id
    )

    # Make sure the conversation gets initialized properly with no errors
    assert conversation2.id == conversation_id
    assert conversation2.agent.llm.api_key is not None
    assert conversation2.agent.llm.api_key.get_secret_value() == "main-key"
    assert isinstance(conversation2.agent.condenser, LLMSummarizingCondenser)
    assert conversation2.agent.condenser.llm.api_key is not None
    assert (
        conversation2.agent.condenser.llm.api_key.get_secret_value() == "condenser-key"
    )

    # Verify that the agent configuration is properly reconciled
    assert conversation2.agent.llm.model == "gpt-4o-mini"
    assert conversation2.agent.condenser.llm.model == "gpt-3.5-turbo"
    assert conversation2.agent.condenser.max_size == 80
    assert conversation2.agent.condenser.keep_first == 10

    # Verify that both conversations reference the same persisted state
    # but with properly reconciled agents
    assert conversation1.id == conversation2.id
    assert conversation1.agent.model_dump(
        exclude_none=True
    ) == conversation2.agent.model_dump(exclude_none=True)


def test_conversation_restart_simple_agent():
    """Test conversation restart with simple agent (no nested LLMs)."""
    # Create a simple agent with only main LLM
    main_llm = LLM(
        model="gpt-4o-mini", api_key=SecretStr("main-key"), service_id="main-llm"
    )

    agent = Agent(llm=main_llm, tools=[])

    # Create a file store for the conversation
    file_store = InMemoryFileStore()
    conversation_id = uuid.uuid4()

    # Create a conversation with the agent + file store
    conversation1 = Conversation(
        agent=agent,
        persist_filestore=file_store,
        conversation_id=conversation_id,
    )

    # Verify the conversation was created successfully
    assert conversation1.id == conversation_id
    assert conversation1.agent.llm.api_key is not None
    assert conversation1.agent.llm.api_key.get_secret_value() == "main-key"

    # Now attempt to restart the conversation
    restart_main_llm = LLM(
        model="gpt-4o-mini", api_key=SecretStr("main-key"), service_id="main-llm"
    )

    restart_agent = Agent(llm=restart_main_llm, tools=[])

    # Attempt to restart the conversation - this should work without errors
    conversation2 = Conversation(
        agent=restart_agent,
        persist_filestore=file_store,
        conversation_id=conversation_id,  # Same conversation_id
    )

    # Make sure the conversation gets initialized properly with no errors
    assert conversation2.id == conversation_id
    assert conversation2.agent.llm.api_key is not None
    assert conversation2.agent.llm.api_key.get_secret_value() == "main-key"
    assert conversation2.agent.llm.model == "gpt-4o-mini"

    # Verify that both conversations are equivalent
    assert conversation1.id == conversation2.id
    assert conversation1.agent.model_dump(
        exclude_none=True
    ) == conversation2.agent.model_dump(exclude_none=True)
