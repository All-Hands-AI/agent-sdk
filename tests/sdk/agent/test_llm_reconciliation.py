"""Test LLM reconciliation logic in agent deserialization."""

import uuid

from pydantic import SecretStr

from openhands.sdk import LocalFileStore
from openhands.sdk.context.condenser.llm_summarizing_condenser import (
    LLMSummarizingCondenser,
)
from openhands.sdk.conversation import Conversation
from openhands.sdk.llm import LLM
from openhands.sdk.preset.default import get_default_agent


def test_conversation_restart_with_nested_llms(tmp_path):
    """Test conversation restart with agent containing nested LLMs."""
    # Create a default agent with dummy LLM + models + keys

    working_dir = str(tmp_path)

    llm = LLM(
        model="gpt-4o-mini", api_key=SecretStr("llm-api-key"), service_id="main-llm"
    )

    # Use the standard Agent class to avoid polymorphic deserialization issues
    agent = get_default_agent(llm, working_dir)

    # Create a file store for the conversation
    file_store = LocalFileStore(root=working_dir)
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
    assert conversation1.agent.llm.api_key.get_secret_value() == "llm-api-key"
    assert isinstance(conversation1.agent.condenser, LLMSummarizingCondenser)
    assert conversation1.agent.condenser.llm.api_key is not None
    assert conversation1.agent.condenser.llm.api_key.get_secret_value() == "llm-api-key"

    # Attempt to restart the conversation - this should work without errors
    conversation2 = Conversation(
        agent=agent,
        persist_filestore=file_store,
        conversation_id=conversation_id,  # Same conversation_id
    )

    # Make sure the conversation gets initialized properly with no errors
    assert conversation2.id == conversation_id
    assert conversation2.agent.llm.api_key is not None
    assert conversation2.agent.llm.api_key.get_secret_value() == "llm-api-key"
    assert isinstance(conversation2.agent.condenser, LLMSummarizingCondenser)
    assert conversation2.agent.condenser.llm.api_key is not None
    assert conversation2.agent.condenser.llm.api_key.get_secret_value() == "llm-api-key"

    # Verify that the agent configuration is properly reconciled
    assert conversation2.agent.llm.model == "gpt-4o-mini"
    assert conversation2.agent.condenser.llm.model == "gpt-4o-mini"
    assert conversation2.agent.condenser.max_size == 80
    assert conversation2.agent.condenser.keep_first == 4


def test_conversation_restarted_with_changed_working_directory(tmp_path_factory):
    working_dir = str(tmp_path_factory.mktemp("persist"))
    path1 = str(tmp_path_factory.mktemp("agent1"))
    path2 = str(tmp_path_factory.mktemp("agent2"))

    llm = LLM(
        model="gpt-4o-mini", api_key=SecretStr("llm-api-key"), service_id="main-llm"
    )

    agent1 = get_default_agent(llm, str(path1))
    file_store = LocalFileStore(root=str(working_dir))
    conversation_id = uuid.uuid4()

    # first conversation
    _ = Conversation(
        agent=agent1, persist_filestore=file_store, conversation_id=conversation_id
    )

    # agent built in a *different* temp dir
    agent2 = get_default_agent(llm, str(path2))

    # restart with new agent working dir but same conversation id
    _ = Conversation(
        agent=agent2, persist_filestore=file_store, conversation_id=conversation_id
    )
