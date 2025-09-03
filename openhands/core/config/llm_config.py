import os

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from openhands.core.logger import ENV_LOG_DIR, get_logger


logger = get_logger(__name__)


class LLMConfig(BaseModel, frozen=True):
    """Immutable configuration for the LLM model.

    Attributes:
        model: The model to use.
        api_key: The API key to use.
        base_url: The base URL for the API. This is necessary for local LLMs.
        api_version: The version of the API.
        aws_access_key_id: The AWS access key ID.
        aws_secret_access_key: The AWS secret access key.
        aws_region_name: The AWS region name.
        num_retries: The number of retries to attempt.
        retry_multiplier: The multiplier for the exponential backoff.
        retry_min_wait: The minimum time to wait between retries, in seconds. This is exponential backoff minimum. For models with very low limits, this can be set to 15-20.
        retry_max_wait: The maximum time to wait between retries, in seconds. This is exponential backoff maximum.
        timeout: The timeout for the API.
        max_message_chars: The approximate max number of characters in the content of an event included in the prompt to the LLM. Larger observations are truncated.
        temperature: The temperature for the API.
        top_p: The top p for the API.
        top_k: The top k for the API.
        custom_llm_provider: The custom LLM provider to use. This is undocumented in openhands, and normally not used. It is documented on the litellm side.
        max_input_tokens: The maximum number of input tokens. Note that this is currently unused, and the value at runtime is actually the total tokens in OpenAI (e.g. 128,000 tokens for GPT-4).
        max_output_tokens: The maximum number of output tokens. This is sent to the LLM.
        input_cost_per_token: The cost per input token. This will available in logs for the user to check.
        output_cost_per_token: The cost per output token. This will available in logs for the user to check.
        ollama_base_url: The base URL for the OLLAMA API.
        drop_params: Drop any unmapped (unsupported) params without causing an exception.
        modify_params: Modify params allows litellm to do transformations like adding a default message, when a message is empty.
        disable_vision: If model is vision capable, this option allows to disable image processing (useful for cost reduction).
        caching_prompt: Use the prompt caching feature if provided by the LLM and supported by the provider.
        log_completions: Whether to log LLM completions to the state.
        log_completions_folder: The folder to log LLM completions to. Required if log_completions is True.
        custom_tokenizer: A custom tokenizer to use for token counting.
        native_tool_calling: Whether to use native tool calling if supported by the model. Can be True, False, or not set.
        reasoning_effort: The effort to put into reasoning. This is a string that can be one of 'low', 'medium', 'high', or 'none'. Can apply to all reasoning models.
        seed: The seed to use for the LLM.
        safety_settings: Safety settings for models that support them (like Mistral AI and Gemini).
    """  # noqa: E501

    model: str = Field(default="claude-sonnet-4-20250514")
    api_key: SecretStr | None = Field(default=None)
    base_url: str | None = Field(default=None)
    api_version: str | None = Field(default=None)
    aws_access_key_id: SecretStr | None = Field(default=None)
    aws_secret_access_key: SecretStr | None = Field(default=None)
    aws_region_name: str | None = Field(default=None)
    openrouter_site_url: str = Field(default="https://docs.all-hands.dev/")
    openrouter_app_name: str = Field(default="OpenHands")
    # total wait time: 8 + 16 + 32 + 64 = 120 seconds
    num_retries: int = Field(default=5)
    retry_multiplier: float = Field(default=8)
    retry_min_wait: int = Field(default=8)
    retry_max_wait: int = Field(default=64)
    timeout: int | None = Field(default=None)
    max_message_chars: int = Field(
        default=30_000
    )  # maximum number of characters in an observation's content when sent to the llm
    temperature: float = Field(default=0.0)
    top_p: float = Field(default=1.0)
    top_k: float | None = Field(default=None)
    custom_llm_provider: str | None = Field(default=None)
    max_input_tokens: int | None = Field(default=None)
    max_output_tokens: int | None = Field(default=None)
    input_cost_per_token: float | None = Field(default=None)
    output_cost_per_token: float | None = Field(default=None)
    ollama_base_url: str | None = Field(default=None)
    # This setting can be sent in each call to litellm
    drop_params: bool = Field(default=True)
    # Note: this setting is actually global, unlike drop_params
    modify_params: bool = Field(default=True)
    disable_vision: bool | None = Field(default=None)
    disable_stop_word: bool | None = Field(default=False)
    caching_prompt: bool = Field(default=True)
    log_completions: bool = Field(default=False)
    log_completions_folder: str = Field(
        default=os.path.join(ENV_LOG_DIR, "completions")
    )
    custom_tokenizer: str | None = Field(default=None)
    native_tool_calling: bool | None = Field(default=None)
    reasoning_effort: str | None = Field(default=None)
    seed: int | None = Field(default=None)
    safety_settings: list[dict[str, str]] | None = Field(
        default=None,
        description=(
            "Safety settings for models that support them (like Mistral AI and Gemini)"
        ),
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _post_validate(self) -> "LLMConfig":
        """
        Runs after all fields are validated. Because the model is frozen,
        we must return a *new* instance with any cross-field updates.
        """
        updates: dict = {}

        # Defaults that depend on other fields
        if self.reasoning_effort is None and "gemini-2.5-pro" not in self.model:
            updates["reasoning_effort"] = "high"

        # Azure API version default
        if self.model.startswith("azure") and self.api_version is None:
            updates["api_version"] = "2024-12-01-preview"

        # Provider rewrite: openhands/* -> litellm_proxy/*
        if self.model.startswith("openhands/"):
            model_name = self.model.removeprefix("openhands/")
            updates["model"] = f"litellm_proxy/{model_name}"
            updates["base_url"] = "https://llm-proxy.app.all-hands.dev/"
            logger.debug(
                f"Rewrote openhands/{model_name} to {updates['model']} with base URL {updates['base_url']}"  # noqa: E501
            )

        if self.model.startswith("huggingface"):
            # HF doesn't support the OpenAI default value for top_p (1)
            logger.debug(f"Setting top_p to 0.9 for Hugging Face model: {self.model}")
            updates["top_p"] = 0.9 if self.top_p == 1 else self.top_p

        # Apply updates in one go (required for frozen models)
        new_self = self.model_copy(update=updates) if updates else self

        # Side effects (env vars) are fine even on frozen models
        if new_self.openrouter_site_url:
            os.environ["OR_SITE_URL"] = new_self.openrouter_site_url
        if new_self.openrouter_app_name:
            os.environ["OR_APP_NAME"] = new_self.openrouter_app_name

        if new_self.aws_access_key_id:
            os.environ["AWS_ACCESS_KEY_ID"] = (
                new_self.aws_access_key_id.get_secret_value()
            )
        if new_self.aws_secret_access_key:
            os.environ["AWS_SECRET_ACCESS_KEY"] = (
                new_self.aws_secret_access_key.get_secret_value()
            )
        if new_self.aws_region_name:
            os.environ["AWS_REGION_NAME"] = new_self.aws_region_name

        logger.debug(
            f"LLMConfig finalized with model={new_self.model} "
            f"base_url={new_self.base_url} "
            f"api_version={new_self.api_version} "
            f"reasoning_effort={new_self.reasoning_effort}",
        )
        return new_self
