"""Test LLM JSON storage and loading functionality."""

import json

from pydantic import SecretStr

from openhands.sdk.io import InMemoryFileStore
from openhands.sdk.llm import LLM


def test_llm_serialize_and_deserialize_with_secrets():
    """Test storing LLM to JSON and loading it back with secrets."""
    # Create original LLM with secrets
    original_llm = LLM(
        model="test-model",
        temperature=0.7,
        max_output_tokens=2000,
        top_p=0.9,
        api_key=SecretStr("secret-api-key"),
        aws_access_key_id=SecretStr("aws-access-key"),
        aws_secret_access_key=SecretStr("aws-secret-key"),
        base_url="https://api.example.com",
        num_retries=3,
    )

    # Store to JSON without exposing secrets
    filestore = InMemoryFileStore()
    filepath = "test_llm.json"
    original_llm.store_to_json(filestore, filepath, expose_secrets=False)

    # Load back from JSON
    stored_content = filestore.read(filepath)
    loaded_data = json.loads(stored_content)
    loaded_llm = LLM.model_validate(loaded_data)

    # Verify basic fields are preserved
    assert loaded_llm.model == original_llm.model
    assert loaded_llm.temperature == original_llm.temperature
    assert loaded_llm.max_output_tokens == original_llm.max_output_tokens
    assert loaded_llm.top_p == original_llm.top_p
    assert loaded_llm.base_url == original_llm.base_url
    assert loaded_llm.num_retries == original_llm.num_retries

    # Verify secrets are masked in the loaded LLM (not the original values)
    assert loaded_llm.api_key is not None
    assert loaded_llm.aws_access_key_id is not None
    assert loaded_llm.aws_secret_access_key is not None
    assert loaded_llm.api_key.get_secret_value() == "**********"
    assert loaded_llm.aws_access_key_id.get_secret_value() == "**********"
    assert loaded_llm.aws_secret_access_key.get_secret_value() == "**********"

    # Verify they are different from original secret values
    assert original_llm.api_key is not None
    assert original_llm.aws_access_key_id is not None
    assert original_llm.aws_secret_access_key is not None
    assert (
        loaded_llm.api_key.get_secret_value() != original_llm.api_key.get_secret_value()
    )
    assert (
        loaded_llm.aws_access_key_id.get_secret_value()
        != original_llm.aws_access_key_id.get_secret_value()
    )
    assert (
        loaded_llm.aws_secret_access_key.get_secret_value()
        != original_llm.aws_secret_access_key.get_secret_value()
    )
