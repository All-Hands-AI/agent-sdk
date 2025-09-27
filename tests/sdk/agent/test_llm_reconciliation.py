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
    llm = LLM(
        model="gpt-4o-mini", api_key=SecretStr("llm-api-key"), service_id="main-llm"
    )

    # Use the standard Agent class to avoid polymorphic deserialization issues
    agent = get_default_agent(llm, tmp_path)

    # Create a file store for the conversation
    file_store = LocalFileStore(root=str(tmp_path))
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
    assert conversation2.agent.condenser.llm.model == "gpt-3.5-turbo"
    assert conversation2.agent.condenser.max_size == 80
    assert conversation2.agent.condenser.keep_first == 10


def test_conversation_restarted_with_changed_secrets():
    pass


def test_conversation_restarted_with_changed_working_directory():
    pass
