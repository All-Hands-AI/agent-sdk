"""Test AgentSpec secret serialization functionality."""

import json

import pytest
from pydantic import SecretStr

from openhands.sdk.agent.spec import AgentSpec
from openhands.sdk.llm import LLM


@pytest.fixture
def llm_with_secrets():
    """Create an LLM with secret fields for testing."""
    return LLM(
        model="test-model",
        api_key=SecretStr("dummy-api-key-123"),
        aws_access_key_id=SecretStr("dummy-aws-access-key"),
        aws_secret_access_key=SecretStr("dummy-aws-secret-key"),
    )


def test_agent_spec_default_serialization_masks_secrets(llm_with_secrets):
    """Test that AgentSpec serialization masks secrets by default."""
    spec = AgentSpec(llm=llm_with_secrets)

    # Test model_dump_json
    json_str = spec.model_dump_json()
    json_data = json.loads(json_str)

    # Verify that secrets are masked in the JSON
    llm_data = json_data["llm"]
    assert llm_data["api_key"] == "**********"
    assert llm_data["aws_access_key_id"] == "**********"
    assert llm_data["aws_secret_access_key"] == "**********"

    # Verify that actual secret values are not in the JSON string
    assert "dummy-api-key-123" not in json_str
    assert "dummy-aws-access-key" not in json_str
    assert "dummy-aws-secret-key" not in json_str


def test_agent_spec_expose_secrets_context_works(llm_with_secrets):
    """Test that expose_secrets context parameter exposes actual secret values."""
    spec = AgentSpec(llm=llm_with_secrets)

    # This should expose secrets when context={'expose_secrets': True}
    json_str = spec.model_dump_json(context={"expose_secrets": True})
    json_data = json.loads(json_str)

    # Verify that secrets are exposed in the JSON
    llm_data = json_data["llm"]
    assert llm_data["api_key"] == "dummy-api-key-123"
    assert llm_data["aws_access_key_id"] == "dummy-aws-access-key"
    assert llm_data["aws_secret_access_key"] == "dummy-aws-secret-key"

    # Verify that actual secret values are in the JSON string
    assert "dummy-api-key-123" in json_str
    assert "dummy-aws-access-key" in json_str
    assert "dummy-aws-secret-key" in json_str


def test_agent_spec_model_dump_masks_secrets(llm_with_secrets):
    """Test that AgentSpec model_dump also masks secrets by default."""
    spec = AgentSpec(llm=llm_with_secrets)

    # Test model_dump
    data = spec.model_dump()

    # Verify that secrets are masked in the dict
    llm_data = data["llm"]
    assert str(llm_data["api_key"]) == "**********"
    assert str(llm_data["aws_access_key_id"]) == "**********"
    assert str(llm_data["aws_secret_access_key"]) == "**********"


def test_llm_with_none_secrets():
    """Test that LLM with None secret fields works correctly."""
    llm = LLM(model="test-model")  # No secrets provided

    # Test default serialization
    json_str = llm.model_dump_json()
    json_data = json.loads(json_str)

    # Verify that None secrets are serialized as null
    assert json_data["api_key"] is None
    assert json_data["aws_access_key_id"] is None
    assert json_data["aws_secret_access_key"] is None

    # Test with expose_secrets=True
    json_str = llm.model_dump_json(context={"expose_secrets": True})
    json_data = json.loads(json_str)

    # Verify that None secrets are still serialized as null
    assert json_data["api_key"] is None
    assert json_data["aws_access_key_id"] is None
    assert json_data["aws_secret_access_key"] is None
