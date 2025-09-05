import os
from unittest.mock import patch

import pytest
from pydantic import SecretStr, ValidationError

from openhands.sdk.config import LLMConfig


def test_llm_config_defaults():
    """Test LLMConfig with default values."""
    config = LLMConfig(model="gpt-4")
    assert config.model == "gpt-4"
    assert config.api_key is None
    assert config.base_url is None
    assert config.api_version is None
    assert config.num_retries == 5
    assert config.retry_multiplier == 8
    assert config.retry_min_wait == 8
    assert config.retry_max_wait == 64
    assert config.timeout is None
    assert config.max_message_chars == 30_000
    assert config.temperature == 0.0
    assert config.top_p == 1.0
    assert config.top_k is None
    assert config.custom_llm_provider is None
    assert config.max_input_tokens is None
    assert config.max_output_tokens is None
    assert config.input_cost_per_token is None
    assert config.output_cost_per_token is None
    assert config.ollama_base_url is None
    assert config.drop_params is True
    assert config.modify_params is True
    assert config.disable_vision is None
    assert config.disable_stop_word is False
    assert config.caching_prompt is True
    assert config.log_completions is False
    assert config.custom_tokenizer is None
    assert config.native_tool_calling is None
    assert config.reasoning_effort == "high"  # Default for non-Gemini models
    assert config.seed is None
    assert config.safety_settings is None


def test_llm_config_custom_values():
    """Test LLMConfig with custom values."""
    config = LLMConfig(
        model="gpt-4",
        api_key=SecretStr("test-key"),
        base_url="https://api.example.com",
        api_version="v1",
        num_retries=3,
        retry_multiplier=2,
        retry_min_wait=1,
        retry_max_wait=10,
        timeout=30,
        max_message_chars=10000,
        temperature=0.5,
        top_p=0.9,
        top_k=50,
        custom_llm_provider="custom",
        max_input_tokens=4000,
        max_output_tokens=1000,
        input_cost_per_token=0.001,
        output_cost_per_token=0.002,
        ollama_base_url="http://localhost:11434",
        drop_params=False,
        modify_params=False,
        disable_vision=True,
        disable_stop_word=True,
        caching_prompt=False,
        log_completions=True,
        custom_tokenizer="custom_tokenizer",
        native_tool_calling=True,
        reasoning_effort="high",
        seed=42,
        safety_settings=[
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            }
        ],
    )

    assert config.model == "gpt-4"
    assert (
        config.api_key is not None and config.api_key.get_secret_value() == "test-key"
    )
    assert config.base_url == "https://api.example.com"
    assert config.api_version == "v1"
    assert config.num_retries == 3
    assert config.retry_multiplier == 2
    assert config.retry_min_wait == 1
    assert config.retry_max_wait == 10
    assert config.timeout == 30
    assert config.max_message_chars == 10000
    assert config.temperature == 0.5
    assert config.top_p == 0.9
    assert config.top_k == 50
    assert config.custom_llm_provider == "custom"
    assert config.max_input_tokens == 4000
    assert config.max_output_tokens == 1000
    assert config.input_cost_per_token == 0.001
    assert config.output_cost_per_token == 0.002
    assert config.ollama_base_url == "http://localhost:11434"
    assert config.drop_params is False
    assert config.modify_params is False
    assert config.disable_vision is True
    assert config.disable_stop_word is True
    assert config.caching_prompt is False
    assert config.log_completions is True
    assert config.custom_tokenizer == "custom_tokenizer"
    assert config.native_tool_calling is True
    assert config.reasoning_effort == "high"
    assert config.seed == 42
    assert config.safety_settings == [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
    ]


def test_llm_config_secret_str():
    """Test that api_key is properly handled as SecretStr."""
    config = LLMConfig(model="gpt-4", api_key=SecretStr("secret-key"))
    assert (
        config.api_key is not None and config.api_key.get_secret_value() == "secret-key"
    )
    # Ensure the secret is not exposed in string representation
    assert "secret-key" not in str(config)


def test_llm_config_aws_credentials():
    """Test AWS credentials handling."""
    config = LLMConfig(
        model="gpt-4",
        aws_access_key_id=SecretStr("test-access-key"),
        aws_secret_access_key=SecretStr("test-secret-key"),
        aws_region_name="us-east-1",
    )
    assert (
        config.aws_access_key_id is not None
        and config.aws_access_key_id.get_secret_value() == "test-access-key"
    )
    assert (
        config.aws_secret_access_key is not None
        and config.aws_secret_access_key.get_secret_value() == "test-secret-key"
    )
    assert config.aws_region_name == "us-east-1"


def test_llm_config_openrouter_defaults():
    """Test OpenRouter default values."""
    config = LLMConfig(model="gpt-4")
    assert config.openrouter_site_url == "https://docs.all-hands.dev/"
    assert config.openrouter_app_name == "OpenHands"


def test_llm_config_post_init_openrouter_env_vars():
    """Test that OpenRouter environment variables are set in post_init."""
    with patch.dict(os.environ, {}, clear=True):
        LLMConfig(
            model="gpt-4",
            openrouter_site_url="https://custom.site.com",
            openrouter_app_name="CustomApp",
        )
        assert os.environ.get("OR_SITE_URL") == "https://custom.site.com"
        assert os.environ.get("OR_APP_NAME") == "CustomApp"


def test_llm_config_post_init_reasoning_effort_default():
    """Test that reasoning_effort is set to 'high' by default for non-Gemini models."""
    config = LLMConfig(model="gpt-4")
    assert config.reasoning_effort == "high"

    # Test that Gemini models don't get default reasoning_effort
    config = LLMConfig(model="gemini-2.5-pro-experimental")
    assert config.reasoning_effort is None


def test_llm_config_post_init_azure_api_version():
    """Test that Azure models get default API version."""
    config = LLMConfig(model="azure/gpt-4")
    assert config.api_version == "2024-12-01-preview"

    # Test that non-Azure models don't get default API version
    config = LLMConfig(model="gpt-4")
    assert config.api_version is None

    # Test that explicit API version is preserved
    config = LLMConfig(model="azure/gpt-4", api_version="custom-version")
    assert config.api_version == "custom-version"


def test_llm_config_post_init_aws_env_vars():
    """Test that AWS credentials are set as environment variables."""
    with patch.dict(os.environ, {}, clear=True):
        LLMConfig(
            model="gpt-4",
            aws_access_key_id=SecretStr("test-access-key"),
            aws_secret_access_key=SecretStr("test-secret-key"),
            aws_region_name="us-west-2",
        )
        assert os.environ.get("AWS_ACCESS_KEY_ID") == "test-access-key"
        assert os.environ.get("AWS_SECRET_ACCESS_KEY") == "test-secret-key"
        assert os.environ.get("AWS_REGION_NAME") == "us-west-2"


def test_llm_config_log_completions_folder_default():
    """Test that log_completions_folder has a default value."""
    config = LLMConfig(model="gpt-4")
    assert config.log_completions_folder is not None
    assert "completions" in config.log_completions_folder


def test_llm_config_extra_fields_forbidden():
    """Test that extra fields are forbidden."""
    with pytest.raises(ValidationError) as exc_info:
        LLMConfig(model="gpt-4", invalid_field="should_not_work")  # type: ignore
    assert "Extra inputs are not permitted" in str(exc_info.value)


def test_llm_config_validation():
    """Test basic validation of LLMConfig fields."""
    # Test that negative values are handled appropriately
    config = LLMConfig(
        model="gpt-4",
        num_retries=-1,  # Should be allowed (might be used to disable retries)
        retry_multiplier=-1,  # Should be allowed
        retry_min_wait=-1,  # Should be allowed
        retry_max_wait=-1,  # Should be allowed
        timeout=-1,  # Should be allowed
        max_message_chars=-1,  # Should be allowed
        temperature=-1,  # Should be allowed
        top_p=-1,  # Should be allowed
    )
    assert config.num_retries == -1
    assert config.retry_multiplier == -1
    assert config.retry_min_wait == -1
    assert config.retry_max_wait == -1
    assert config.timeout == -1
    assert config.max_message_chars == -1
    assert config.temperature == -1
    assert config.top_p == -1


def test_llm_config_model_variants():
    """Test various model name formats."""
    models = [
        "gpt-4",
        "claude-3-sonnet",
        "azure/gpt-4",
        "anthropic/claude-3-sonnet",
        "gemini-2.5-pro-experimental",
        "local/custom-model",
    ]

    for model in models:
        config = LLMConfig(model=model)
        assert config.model == model


def test_llm_config_boolean_fields():
    """Test boolean field handling."""
    config = LLMConfig(
        model="gpt-4",
        drop_params=True,
        modify_params=False,
        disable_vision=True,
        disable_stop_word=False,
        caching_prompt=True,
        log_completions=False,
        native_tool_calling=True,
    )

    assert config.drop_params is True
    assert config.modify_params is False
    assert config.disable_vision is True
    assert config.disable_stop_word is False
    assert config.caching_prompt is True
    assert config.log_completions is False
    assert config.native_tool_calling is True


def test_llm_config_optional_fields():
    """Test that optional fields can be None."""
    config = LLMConfig(
        model="gpt-4",
        api_key=None,
        base_url=None,
        api_version=None,
        aws_access_key_id=None,
        aws_secret_access_key=None,
        aws_region_name=None,
        timeout=None,
        top_k=None,
        custom_llm_provider=None,
        max_input_tokens=None,
        max_output_tokens=None,
        input_cost_per_token=None,
        output_cost_per_token=None,
        ollama_base_url=None,
        disable_vision=None,
        disable_stop_word=None,
        custom_tokenizer=None,
        native_tool_calling=None,
        reasoning_effort=None,
        seed=None,
        safety_settings=None,
    )

    assert config.api_key is None
    assert config.base_url is None
    assert config.api_version is None
    assert config.aws_access_key_id is None
    assert config.aws_secret_access_key is None
    assert config.aws_region_name is None
    assert config.timeout is None
    assert config.top_k is None
    assert config.custom_llm_provider is None
    assert config.max_input_tokens is None
    assert config.max_output_tokens is None
    assert config.input_cost_per_token is None
    assert config.output_cost_per_token is None
    assert config.ollama_base_url is None
    assert config.disable_vision is None
    assert config.disable_stop_word is None
    assert config.custom_tokenizer is None
    assert config.native_tool_calling is None
    assert (
        config.reasoning_effort == "high"
    )  # Even when set to None, post_init sets it to "high" for non-Gemini models
    assert config.seed is None
    assert config.safety_settings is None
