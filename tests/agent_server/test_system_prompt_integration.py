"""Test system prompt integration with agent server."""

import json

from openhands.agent_server.models import StartConversationRequest
from openhands.sdk import LLM, Agent
from openhands.sdk.agent.base import AgentBase


def test_start_conversation_request_with_custom_system_prompt():
    """Test that StartConversationRequest properly handles custom system prompt."""
    custom_prompt = "You are a helpful AI assistant specialized in code review."
    llm = LLM(model="test-model", service_id="test-llm")
    agent = Agent(llm=llm, tools=[], system_prompt=custom_prompt)

    # Create StartConversationRequest
    request = StartConversationRequest(agent=agent)

    # Should include the agent with custom system prompt
    assert request.agent.system_prompt == custom_prompt
    assert request.agent.system_message == custom_prompt


def test_start_conversation_request_serialization_with_system_prompt():
    """Test that StartConversationRequest serializes custom system prompt correctly."""
    custom_prompt = "You are a helpful AI assistant specialized in code review."
    llm = LLM(model="test-model", service_id="test-llm")
    agent = Agent(llm=llm, tools=[], system_prompt=custom_prompt)

    # Create and serialize StartConversationRequest
    request = StartConversationRequest(agent=agent)
    request_dict = request.model_dump()

    # Should include system_prompt in the agent data
    assert "agent" in request_dict
    assert "system_prompt" in request_dict["agent"]
    assert request_dict["agent"]["system_prompt"] == custom_prompt


def test_start_conversation_request_json_roundtrip_with_system_prompt():
    """Test that StartConversationRequest survives JSON roundtrip with custom system prompt."""  # noqa: E501
    custom_prompt = "You are a helpful AI assistant specialized in code review."
    llm = LLM(model="test-model", service_id="test-llm")
    agent = Agent(llm=llm, tools=[], system_prompt=custom_prompt)

    # Create StartConversationRequest
    request = StartConversationRequest(agent=agent)

    # Serialize to JSON
    request_json = request.model_dump_json()

    # Deserialize from JSON
    deserialized_request = StartConversationRequest.model_validate_json(request_json)

    # Should preserve the custom system prompt
    assert isinstance(deserialized_request.agent, Agent)
    assert deserialized_request.agent.system_prompt == custom_prompt
    assert deserialized_request.agent.system_message == custom_prompt


def test_agent_serialization_in_conversation_payload():
    """Test that agent serialization for conversation API includes system prompt."""
    custom_prompt = "You are a helpful AI assistant specialized in code review."
    llm = LLM(model="test-model", service_id="test-llm")
    agent = Agent(llm=llm, tools=[], system_prompt=custom_prompt)

    # Simulate the payload creation as done in RemoteConversation
    payload = {
        "agent": agent.model_dump(mode="json", context={"expose_secrets": True}),
        "initial_message": None,
        "max_iterations": 500,
        "stuck_detection": True,
    }

    # Should include system_prompt in the agent data
    assert "system_prompt" in payload["agent"]
    assert payload["agent"]["system_prompt"] == custom_prompt

    # Should be JSON serializable
    json_payload = json.dumps(payload)
    parsed_payload = json.loads(json_payload)

    # Should preserve system_prompt after JSON roundtrip
    assert parsed_payload["agent"]["system_prompt"] == custom_prompt

    # Should be able to reconstruct the agent
    reconstructed_agent = AgentBase.model_validate(parsed_payload["agent"])
    assert isinstance(reconstructed_agent, Agent)
    assert reconstructed_agent.system_prompt == custom_prompt
    assert reconstructed_agent.system_message == custom_prompt


def test_agent_without_custom_system_prompt_in_conversation():
    """Test that agent without custom system prompt works correctly in conversation."""
    llm = LLM(model="test-model", service_id="test-llm")
    agent = Agent(llm=llm, tools=[])  # No custom system_prompt

    # Create StartConversationRequest
    request = StartConversationRequest(agent=agent)

    # Should have None for system_prompt but valid system_message
    assert request.agent.system_prompt is None
    assert isinstance(request.agent.system_message, str)
    assert len(request.agent.system_message) > 0

    # Should serialize correctly
    request_dict = request.model_dump()
    assert request_dict["agent"]["system_prompt"] is None

    # Should survive JSON roundtrip
    request_json = request.model_dump_json()
    deserialized_request = StartConversationRequest.model_validate_json(request_json)
    assert deserialized_request.agent.system_prompt is None
    assert isinstance(deserialized_request.agent.system_message, str)
