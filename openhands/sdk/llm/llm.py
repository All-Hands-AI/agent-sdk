import copy
import json as json_module
import os
import time
import warnings
from functools import partial
from typing import Any, Callable, Literal, TypeGuard, cast

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from openhands.sdk.llm.utils.metrics import Metrics
from openhands.sdk.llm.utils.model_features import get_features
from openhands.sdk.logger import ENV_LOG_DIR, get_logger


with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import litellm

from litellm import Message as LiteLLMMessage, completion as litellm_completion
from litellm.cost_calculator import completion_cost as litellm_completion_cost
from litellm.exceptions import (
    APIConnectionError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout as LiteLLMTimeout,
)
from litellm.types.utils import (
    Choices,
    CostPerToken,
    ModelResponse,
    PromptTokensDetailsWrapper,
    StreamingChoices,
    Usage,
)
from litellm.utils import (
    create_pretrained_tokenizer,
    get_model_info,
    supports_vision,
    token_counter,
)

from openhands.sdk.llm.exceptions import LLMNoResponseError
from openhands.sdk.llm.message import Message
from openhands.sdk.llm.utils.fn_call_converter import (
    STOP_WORDS,
    convert_fncall_messages_to_non_fncall_messages,
    convert_non_fncall_messages_to_fncall_messages,
)
from openhands.sdk.llm.utils.retry_mixin import RetryMixin


logger = get_logger(__name__)

__all__ = ["LLM"]

# tuple of exceptions to retry on
LLM_RETRY_EXCEPTIONS: tuple[type[Exception], ...] = (
    APIConnectionError,
    RateLimitError,
    ServiceUnavailableError,
    LiteLLMTimeout,
    InternalServerError,
    LLMNoResponseError,
)


class LLM(BaseModel, RetryMixin):
    """The LLM class represents a Language Model instance with integrated configuration.

    This class combines both configuration and functionality, eliminating the need
    for a separate LLMConfig class. It can be instantiated directly with configuration
    parameters and provides serialization/deserialization capabilities.
    """

    model: str = Field(
        default="claude-sonnet-4-20250514", description="The model to use."
    )
    api_key: SecretStr | None = Field(default=None, description="The API key to use.")
    base_url: str | None = Field(
        default=None,
        description="The base URL for the API. This is necessary for local LLMs.",
    )
    api_version: str | None = Field(default=None, description="The version of the API.")
    aws_access_key_id: SecretStr | None = Field(
        default=None, description="The AWS access key ID."
    )
    aws_secret_access_key: SecretStr | None = Field(
        default=None, description="The AWS secret access key."
    )
    aws_region_name: str | None = Field(
        default=None, description="The AWS region name."
    )
    openrouter_site_url: str = Field(default="https://docs.all-hands.dev/")
    openrouter_app_name: str = Field(default="OpenHands")
    # total wait time: 8 + 16 + 32 + 64 = 120 seconds
    num_retries: int = Field(default=5, description="The number of retries to attempt.")
    retry_multiplier: float = Field(
        default=8, description="The multiplier for the retry wait time."
    )
    retry_min_wait: int = Field(
        default=8,
        description="The minimum time to wait between retries, in seconds. "
        "This is exponential backoff minimum. For models with very low limits, "
        "this can be set to 15-20.",
    )
    retry_max_wait: int = Field(
        default=64,
        description="The maximum time to wait between retries, in seconds. "
        "This is exponential backoff maximum.",
    )
    timeout: int | None = Field(
        default=None, description="The timeout for the API request."
    )
    max_message_chars: int = Field(
        default=30_000,
        description="The approximate max number of characters in the content of an"
        " event included in the prompt to the LLM. Larger observations are truncated.",
    )  # maximum number of characters in an observation's content when sent to the llm
    temperature: float = Field(default=0.0, description="The temperature for the API.")
    top_p: float = Field(
        default=1.0, description="The top-p (nucleus) sampling parameter for the API."
    )
    top_k: float | None = Field(
        default=None, description="The top-k sampling parameter for the API."
    )
    custom_llm_provider: str | None = Field(
        default=None,
        description="The custom LLM provider to use. "
        "This is undocumented in openhands, and normally not used. "
        "It is documented on the litellm side.",
    )  # noqa: E501
    max_input_tokens: int | None = Field(
        default=None,
        description="The maximum number of input tokens. "
        "Note that this is currently unused, and the value at runtime is actually"
        " the total tokens in OpenAI (e.g. 128,000 tokens for GPT-4).",
    )
    max_output_tokens: int | None = Field(
        default=None,
        description="The maximum number of output tokens. This is sent to the LLM.",
    )
    input_cost_per_token: float | None = Field(
        default=None,
        description="The cost per input token. This will available in logs for user.",
    )
    output_cost_per_token: float | None = Field(
        default=None,
        description="The cost per output token. This will available in logs for user.",
    )
    ollama_base_url: str | None = Field(
        default=None, description="The base URL for the OLLAMA API."
    )
    drop_params: bool = Field(
        default=True,
        description="Drop any unmapped (unsupported) params "
        "without causing an exception.",
    )
    # Note: this setting is actually global, unlike drop_params
    modify_params: bool = Field(
        default=True,
        description="Modify params allows litellm to do transformations like adding"
        " a default message, when a message is empty.",
    )
    disable_vision: bool | None = Field(
        default=None,
        description="If model is vision capable, this option allows to disable image "
        "processing (useful for cost reduction).",
    )
    disable_stop_word: bool | None = Field(
        default=False, description="Disable using of stop word."
    )
    caching_prompt: bool = Field(default=True, description="Enable caching of prompts.")
    log_completions: bool = Field(
        default=False, description="Enable logging of completions."
    )
    log_completions_folder: str = Field(
        default=os.path.join(ENV_LOG_DIR, "completions"),
        description="The folder to log LLM completions to. "
        "Required if log_completions is True.",
    )
    custom_tokenizer: str | None = Field(
        default=None, description="A custom tokenizer to use for token counting."
    )
    native_tool_calling: bool | None = Field(
        default=None,
        description="Whether to use native tool calling "
        "if supported by the model. Can be True, False, or not set.",
    )
    reasoning_effort: Literal["low", "medium", "high", "none"] | None = Field(
        default=None,
        description="The effort to put into reasoning. "
        "This is a string that can be one of 'low', 'medium', 'high', or 'none'. "
        "Can apply to all reasoning models.",
    )
    seed: int | None = Field(
        default=None, description="The seed to use for random number generation."
    )
    safety_settings: list[dict[str, str]] | None = Field(
        default=None,
        description=(
            "Safety settings for models that support them (like Mistral AI and Gemini)"
        ),
    )

    # Runtime fields (not part of configuration)
    service_id: str = Field(default="default", exclude=True)
    metrics: Metrics | None = Field(default=None, exclude=True)
    retry_listener: Callable[[int, int], None] | None = Field(
        default=None, exclude=True
    )

    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,  # For Metrics and Callable types
    )

    # Dynamic attributes set in __post_init__ (for type checking)
    model_info: Any = None
    tokenizer: Any = None
    cost_metric_supported: bool = False
    _completion: Any = None
    _completion_unwrapped: Any = None
    _tried_model_info: bool = False
    _function_calling_active: bool = False

    # 1) Pre-validation: transform inputs for a frozen model
    @model_validator(mode="before")
    @classmethod
    def _coerce_inputs(cls, data):
        # data can be dict or BaseModel – normalize to dict
        if not isinstance(data, dict):
            return data
        d = dict(data)

        model_val = d.get("model", None)
        if model_val is None:
            raise ValueError("model must be specified in LLM")

        # reasoning_effort default (unless Gemini)
        if d.get("reasoning_effort") is None and "gemini-2.5-pro" not in model_val:
            d["reasoning_effort"] = "high"

        # Azure default api_version
        if model_val.startswith("azure") and not d.get("api_version"):
            d["api_version"] = "2024-12-01-preview"

        # Provider rewrite: openhands/* -> litellm_proxy/*
        if model_val.startswith("openhands/"):
            model_name = model_val.removeprefix("openhands/")
            d["model"] = f"litellm_proxy/{model_name}"
            # don't overwrite if caller explicitly set base_url
            d.setdefault("base_url", "https://llm-proxy.app.all-hands.dev/")

        # HF doesn't support the OpenAI default value for top_p (1)
        if model_val.startswith("huggingface"):
            logger.debug(f"Setting top_p to 0.9 for Hugging Face model: {model_val}")
            _cur_top_p = d.get("top_p", 1.0)
            d["top_p"] = 0.9 if _cur_top_p == 1 else _cur_top_p

        return d

    # 2) Post-validation: side effects only; must return self
    @model_validator(mode="after")
    def _set_env_side_effects(self):
        if self.openrouter_site_url:
            os.environ["OR_SITE_URL"] = self.openrouter_site_url
        if self.openrouter_app_name:
            os.environ["OR_APP_NAME"] = self.openrouter_app_name

        if self.aws_access_key_id:
            os.environ["AWS_ACCESS_KEY_ID"] = self.aws_access_key_id.get_secret_value()
        if self.aws_secret_access_key:
            os.environ["AWS_SECRET_ACCESS_KEY"] = (
                self.aws_secret_access_key.get_secret_value()
            )
        if self.aws_region_name:
            os.environ["AWS_REGION_NAME"] = self.aws_region_name

        logger.debug(
            f"LLM finalized with model={self.model} "
            f"base_url={self.base_url} "
            f"api_version={self.api_version} "
            f"reasoning_effort={self.reasoning_effort}",
        )
        return self

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "LLM":
        """Deserialize LLM from dictionary data.

        Args:
            data: Dictionary containing LLM configuration data.

        Returns:
            LLM instance.
        """
        return cls(**data)

    def serialize(self) -> dict[str, Any]:
        """Serialize LLM to dictionary data.

        Returns:
            Dictionary containing LLM configuration data.
        """
        return self.model_dump(exclude={"service_id", "metrics", "retry_listener"})

    @classmethod
    def load_from_json(cls, json_path: str) -> "LLM":
        """Load LLM configuration from JSON file.

        Args:
            json_path: Path to JSON file containing LLM configuration.

        Returns:
            LLM instance.
        """
        with open(json_path, "r") as f:
            data = json_module.load(f)
        return cls.deserialize(data)

    @classmethod
    def load_from_env(cls, prefix: str = "LLM_") -> "LLM":
        """Load LLM configuration from environment variables.

        Args:
            prefix: Prefix for environment variables (default: "LLM_").

        Returns:
            LLM instance.
        """
        data = {}
        for key, value in os.environ.items():
            if key.startswith(prefix):
                field_name = key[len(prefix) :].lower()
                # Handle special cases for secret fields
                if field_name in (
                    "api_key",
                    "aws_access_key_id",
                    "aws_secret_access_key",
                ):
                    data[field_name] = SecretStr(value)
                # Handle boolean fields
                elif field_name in (
                    "drop_params",
                    "modify_params",
                    "disable_vision",
                    "disable_stop_word",
                    "caching_prompt",
                    "log_completions",
                    "native_tool_calling",
                ):
                    data[field_name] = value.lower() in ("true", "1", "yes", "on")
                # Handle numeric fields
                elif field_name in (
                    "num_retries",
                    "retry_min_wait",
                    "retry_max_wait",
                    "timeout",
                    "max_message_chars",
                    "max_input_tokens",
                    "max_output_tokens",
                    "seed",
                ):
                    try:
                        data[field_name] = int(value)
                    except ValueError:
                        continue
                elif field_name in (
                    "retry_multiplier",
                    "temperature",
                    "top_p",
                    "top_k",
                    "input_cost_per_token",
                    "output_cost_per_token",
                ):
                    try:
                        data[field_name] = float(value)
                    except ValueError:
                        continue
                else:
                    data[field_name] = value
        return cls.deserialize(data)

    @classmethod
    def load_from_toml(cls, toml_path: str) -> "LLM":
        """Load LLM configuration from TOML file.

        Args:
            toml_path: Path to TOML file containing LLM configuration.

        Returns:
            LLM instance.
        """
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore # fallback for Python < 3.11
            except ImportError:
                raise ImportError("tomllib or tomli is required to load TOML files")

        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        # Handle nested structure if LLM config is under a section
        if "llm" in data:
            data = data["llm"]

        return cls.deserialize(data)

    def __init__(
        self,
        service_id: str = "default",
        metrics: Metrics | None = None,
        retry_listener: Callable[[int, int], None] | None = None,
        **data: Any,
    ) -> None:
        """Initializes the LLM with configuration and runtime parameters.

        Args:
            service_id: The service ID for this LLM instance.
            metrics: The metrics to use.
            retry_listener: Optional callback for retry events.
            **data: Configuration parameters (model, api_key, etc.)
        """
        super().__init__(
            service_id=service_id,
            metrics=metrics,
            retry_listener=retry_listener,
            **data,
        )

        # Initialize runtime attributes using object.__setattr__ for pydantic models
        object.__setattr__(self, "_tried_model_info", False)
        object.__setattr__(self, "cost_metric_supported", True)
        if self.metrics is None:
            object.__setattr__(self, "metrics", Metrics(model_name=self.model))

        object.__setattr__(self, "model_info", None)
        object.__setattr__(self, "_function_calling_active", False)
        # max_input_tokens is already set as a field, no need to copy it
        if self.log_completions:
            if self.log_completions_folder is None:
                raise RuntimeError(
                    "log_completions_folder is required when log_completions is enabled"
                )
            os.makedirs(self.log_completions_folder, exist_ok=True)

        # call init_model_info to initialize max_output_tokens
        # which is used in partial function
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.init_model_info()
        if self.vision_is_active():
            logger.debug("LLM: model has vision enabled")
        if self.is_caching_prompt_active():
            logger.debug("LLM: caching prompt enabled")
        if self.is_function_calling_active():
            logger.debug("LLM: model supports function calling")

        # if using a custom tokenizer, make sure it's loaded and accessible in the format expected by litellm  # noqa: E501
        if self.custom_tokenizer is not None:
            object.__setattr__(
                self, "tokenizer", create_pretrained_tokenizer(self.custom_tokenizer)
            )
        else:
            object.__setattr__(self, "tokenizer", None)

        # set up the completion function
        kwargs: dict[str, Any] = {
            "temperature": self.temperature,
            "max_completion_tokens": self.max_output_tokens,
        }
        if self.top_k is not None:
            # openai doesn't expose top_k
            # litellm will handle it a bit differently than the openai-compatible params
            kwargs["top_k"] = self.top_k
        if self.top_p is not None:
            # openai doesn't expose top_p, but litellm does
            kwargs["top_p"] = self.top_p

        features = get_features(self.model)
        if features.supports_reasoning_effort:
            # For Gemini models, only map 'low' to optimized thinking budget
            # Let other reasoning_effort values pass through to API as-is
            if "gemini-2.5-pro" in self.model:
                logger.debug(
                    f"Gemini model {self.model} with reasoning_effort {self.reasoning_effort}"  # noqa: E501
                )
                if self.reasoning_effort in {None, "low", "none"}:
                    kwargs["thinking"] = {"budget_tokens": 128}
                    kwargs["allowed_openai_params"] = ["thinking"]
                    kwargs.pop("reasoning_effort", None)
                else:
                    kwargs["reasoning_effort"] = self.reasoning_effort
                logger.debug(
                    f"Gemini model {self.model} with reasoning_effort {self.reasoning_effort} mapped to thinking {kwargs.get('thinking')}"  # noqa: E501
                )

            else:
                kwargs["reasoning_effort"] = self.reasoning_effort
            kwargs.pop(
                "temperature"
            )  # temperature is not supported for reasoning models
            kwargs.pop("top_p")  # reasoning model like o3 doesn't support top_p
        # Azure issue: https://github.com/All-Hands-AI/OpenHands/issues/6777
        if self.model.startswith("azure"):
            kwargs["max_tokens"] = self.max_output_tokens
            kwargs.pop("max_completion_tokens")

        # Add safety settings for models that support them
        if "mistral" in self.model.lower() and self.safety_settings:
            kwargs["safety_settings"] = self.safety_settings
        elif "gemini" in self.model.lower() and self.safety_settings:
            kwargs["safety_settings"] = self.safety_settings

        # Explicitly disable Anthropic extended thinking for Opus 4.1 to avoid
        # requiring 'thinking' content blocks. See issue #10510.
        if "claude-opus-4-1" in self.model.lower():
            kwargs["thinking"] = {"type": "disabled"}

        # Anthropic constraint: Opus models cannot accept both temperature and top_p
        # Prefer temperature (drop top_p) if both are specified.
        _model_lower = self.model.lower()
        # Limit to Opus 4.1 specifically to avoid changing behavior of other Anthropic models  # noqa: E501
        if ("claude-opus-4-1" in _model_lower) and (
            "temperature" in kwargs and "top_p" in kwargs
        ):
            kwargs.pop("top_p", None)

        object.__setattr__(
            self,
            "_completion",
            partial(
                litellm_completion,
                model=self.model,
                api_key=self.api_key.get_secret_value() if self.api_key else None,
                base_url=self.base_url,
                api_version=self.api_version,
                custom_llm_provider=self.custom_llm_provider,
                timeout=self.timeout,
                drop_params=self.drop_params,
                seed=self.seed,
                **kwargs,
            ),
        )

        object.__setattr__(self, "_completion_unwrapped", self._completion)  # type: ignore[assignment]  # noqa: E501

        @self.retry_decorator(
            num_retries=self.num_retries,
            retry_exceptions=LLM_RETRY_EXCEPTIONS,
            retry_min_wait=self.retry_min_wait,
            retry_max_wait=self.retry_max_wait,
            retry_multiplier=self.retry_multiplier,
            retry_listener=self.retry_listener,
        )
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrapper for the litellm completion function. Logs the input and output of the completion function."""  # noqa: E501
            from openhands.sdk.utils import json

            if "stream" in kwargs and kwargs["stream"]:
                raise ValueError("Streaming is not supported in LLM class.")

            messages_kwarg: (
                dict[str, Any] | Message | list[dict[str, Any]] | list[Message]
            ) = []
            mock_function_calling = not self.is_function_calling_active()

            # some callers might send the model and messages directly
            # litellm allows positional args, like completion(model, messages, **kwargs)
            if len(args) > 1:
                # ignore the first argument if it's provided (it would be the model)
                # design wise: we don't allow overriding the configured values
                # implementation wise: the partial function set the model as a kwarg already  # noqa: E501
                # as well as other kwargs
                messages_kwarg = args[1] if len(args) > 1 else args[0]
                kwargs["messages"] = messages_kwarg

                # remove the first args, they're sent in kwargs
                args = args[2:]
            elif "messages" in kwargs:
                messages_kwarg = kwargs["messages"]

            # ensure we work with a list of messages
            messages_list = (
                messages_kwarg if isinstance(messages_kwarg, list) else [messages_kwarg]
            )
            # format Message objects to dict if needed
            messages: list[dict] = []
            if messages_list and isinstance(messages_list[0], Message):
                messages = self.format_messages_for_llm(
                    cast(list[Message], messages_list)
                )
            else:
                messages = cast(list[dict[str, Any]], messages_list)

            kwargs["messages"] = messages

            # handle conversion of to non-function calling messages if needed
            original_fncall_messages = copy.deepcopy(messages)
            mock_fncall_tools = None
            # if the agent or caller has defined tools, and we mock via prompting, convert the messages  # noqa: E501
            if mock_function_calling and "tools" in kwargs:
                add_in_context_learning_example = True
                if "openhands-lm" in self.model or "devstral" in self.model:
                    add_in_context_learning_example = False

                messages = convert_fncall_messages_to_non_fncall_messages(
                    messages,
                    kwargs["tools"],
                    add_in_context_learning_example=add_in_context_learning_example,
                )
                kwargs["messages"] = messages

                # add stop words if the model supports it and stop words are not disabled  # noqa: E501
                if (
                    get_features(self.model).supports_stop_words
                    and not self.disable_stop_word
                ):
                    kwargs["stop"] = STOP_WORDS

                mock_fncall_tools = kwargs.pop("tools")
                if "openhands-lm" in self.model:
                    # If we don't have this, we might run into issue when serving openhands-lm  # noqa: E501
                    # using SGLang
                    # BadRequestError: litellm.BadRequestError: OpenAIException - Error code: 400 - {'object': 'error', 'message': '400', 'type': 'Failed to parse fc related info to json format!', 'param': None, 'code': 400}  # noqa: E501
                    kwargs["tool_choice"] = "none"
                else:
                    # tool_choice should not be specified when mocking function calling
                    kwargs.pop("tool_choice", None)

            # if we have no messages, something went very wrong
            if not messages:
                raise ValueError(
                    "The messages list is empty. At least one message is required."
                )

            # set litellm modify_params to the configured value
            # True by default to allow litellm to do transformations like adding a default message, when a message is empty  # noqa: E501
            # NOTE: this setting is global; unlike drop_params, it cannot be overridden in the litellm completion partial  # noqa: E501
            litellm.modify_params = self.modify_params

            # if we're not using litellm proxy, remove the extra_body
            if "litellm_proxy" not in self.model:
                kwargs.pop("extra_body", None)

            # Record start time for latency measurement
            start_time = time.time()
            # we don't support streaming here, thus we get a ModelResponse

            # Suppress httpx deprecation warnings during LiteLLM calls
            # This prevents the "Use 'content=<...>' to upload raw bytes/text content" warning  # noqa: E501
            # that appears when LiteLLM makes HTTP requests to LLM providers
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", category=DeprecationWarning, module="httpx.*"
                )
                warnings.filterwarnings(
                    "ignore",
                    message=r".*content=.*upload.*",
                    category=DeprecationWarning,
                )
                resp: ModelResponse = self._completion_unwrapped(*args, **kwargs)

            # Calculate and record latency
            latency = time.time() - start_time
            response_id = resp.get("id", "unknown") or "unknown"
            if self.metrics:
                self.metrics.add_response_latency(latency, response_id)

            non_fncall_response = copy.deepcopy(resp)

            # if we mocked function calling, and we have tools, convert the response back to function calling format  # noqa: E501
            if mock_function_calling and mock_fncall_tools is not None:
                if len(resp.choices) < 1:
                    raise LLMNoResponseError(
                        "Response choices is less than 1 - This is only seen in Gemini models so far. Response: "  # noqa: E501
                        + str(resp)
                    )

                # For type checking: it is not possible to get StreamingChoices here
                def _all_choices(
                    items: list[Choices | StreamingChoices],
                ) -> TypeGuard[list[Choices]]:
                    return all(isinstance(c, Choices) for c in items)

                if not _all_choices(resp.choices):
                    raise AssertionError(
                        "Expected non-streaming Choices (no StreamingChoices) here"
                    )

                non_fncall_response_message: dict = resp.choices[0].message.model_dump()
                # messages is already a list with proper typing from line 223
                fn_call_messages_with_response = (
                    convert_non_fncall_messages_to_fncall_messages(
                        messages + [non_fncall_response_message], mock_fncall_tools
                    )
                )
                fn_call_response_message = fn_call_messages_with_response[-1]
                if not isinstance(fn_call_response_message, LiteLLMMessage):
                    fn_call_response_message = LiteLLMMessage(
                        **fn_call_response_message
                    )
                resp.choices[0].message = fn_call_response_message

            # Check if resp has 'choices' key with at least one item
            if not resp.get("choices") or len(resp["choices"]) < 1:
                raise LLMNoResponseError(
                    "Response choices is less than 1 - This is only seen in Gemini models so far. Response: "  # noqa: E501
                    + str(resp)
                )

            # post-process the response first to calculate cost
            cost = self._post_completion(resp)

            # log for evals or other scripts that need the raw completion
            if self.log_completions:
                assert self.log_completions_folder is not None
                log_file = os.path.join(
                    self.log_completions_folder,
                    f"{self.model.replace('/', '__')}-{time.time()}.json",
                )

                # set up the dict to be logged
                _d = {
                    "messages": messages,
                    "response": resp,
                    "args": args,
                    "kwargs": {
                        k: v
                        for k, v in kwargs.items()
                        if k not in ("messages", "client")
                    },
                    "timestamp": time.time(),
                    "cost": cost,
                }

                # if non-native function calling, save messages/response separately
                if mock_function_calling:
                    # Overwrite response as non-fncall to be consistent with messages
                    _d["response"] = non_fncall_response

                    # Save fncall_messages/response separately
                    _d["fncall_messages"] = original_fncall_messages
                    _d["fncall_response"] = resp
                with open(log_file, "w") as f:
                    f.write(json.dumps(_d))

            return resp

        object.__setattr__(self, "_completion", wrapper)

    @property
    def completion(self) -> Callable:
        """Decorator for the litellm completion function.

        Check the complete documentation at https://litellm.vercel.app/docs/completion
        """
        return self._completion

    def init_model_info(self) -> None:
        if self._tried_model_info:
            return
        object.__setattr__(self, "_tried_model_info", True)
        try:
            if self.model.startswith("openrouter"):
                object.__setattr__(self, "model_info", get_model_info(self.model))
        except Exception as e:
            logger.debug(f"Error getting model info: {e}")

        if self.model.startswith("litellm_proxy/"):
            # IF we are using LiteLLM proxy, get model info from LiteLLM proxy
            # GET {base_url}/v1/model/info with litellm_model_id as path param
            base_url = self.base_url.strip() if self.base_url else ""
            if not base_url.startswith(("http://", "https://")):
                base_url = "http://" + base_url

            response = httpx.get(
                f"{base_url}/v1/model/info",
                headers={
                    "Authorization": f"Bearer {self.api_key.get_secret_value() if self.api_key else None}"  # noqa: E501
                },
            )

            try:
                resp_json = response.json()
                if "data" not in resp_json:
                    logger.info(
                        f"No data field in model info response from LiteLLM proxy: {resp_json}"  # noqa: E501
                    )
                all_model_info = resp_json.get("data", [])
            except Exception as e:
                logger.info(f"Error parsing JSON response from LiteLLM proxy: {e}")
                all_model_info = []
            current_model_info = next(
                (
                    info
                    for info in all_model_info
                    if info["model_name"] == self.model.removeprefix("litellm_proxy/")
                ),
                None,
            )
            if current_model_info:
                object.__setattr__(self, "model_info", current_model_info["model_info"])
                logger.debug(f"Got model info from litellm proxy: {self.model_info}")

        # Last two attempts to get model info from NAME
        if not self.model_info:
            try:
                object.__setattr__(
                    self, "model_info", get_model_info(self.model.split(":")[0])
                )
            # noinspection PyBroadException
            except Exception:
                pass
        if not self.model_info:
            try:
                object.__setattr__(
                    self, "model_info", get_model_info(self.model.split("/")[-1])
                )
            # noinspection PyBroadException
            except Exception:
                pass

        from openhands.sdk.utils import json

        logger.debug(
            f"Model info: {json.dumps({'model': self.model, 'base_url': self.base_url}, indent=2)}"  # noqa: E501
        )

        # Set max_input_tokens from model info if not explicitly set
        if (
            self.max_input_tokens is None
            and self.model_info is not None
            and "max_input_tokens" in self.model_info
            and isinstance(self.model_info["max_input_tokens"], int)
        ):
            object.__setattr__(
                self, "max_input_tokens", self.model_info["max_input_tokens"]
            )

        # Set max_output_tokens from model info if not explicitly set
        if self.max_output_tokens is None:
            # Special case for Claude 3.7 Sonnet models
            if any(
                model in self.model
                for model in ["claude-3-7-sonnet", "claude-3.7-sonnet"]
            ):
                object.__setattr__(
                    self, "max_output_tokens", 64000
                )  # litellm set max to 128k, but that requires a header to be set  # noqa: E501
            # Try to get from model info
            elif self.model_info is not None:
                # max_output_tokens has precedence over max_tokens
                if "max_output_tokens" in self.model_info and isinstance(
                    self.model_info["max_output_tokens"], int
                ):
                    object.__setattr__(
                        self, "max_output_tokens", self.model_info["max_output_tokens"]
                    )
                elif "max_tokens" in self.model_info and isinstance(
                    self.model_info["max_tokens"], int
                ):
                    object.__setattr__(
                        self, "max_output_tokens", self.model_info["max_tokens"]
                    )

        # Initialize function calling using centralized model features
        features = get_features(self.model)
        if self.native_tool_calling is None:
            object.__setattr__(
                self, "_function_calling_active", features.supports_function_calling
            )
        else:
            object.__setattr__(
                self, "_function_calling_active", self.native_tool_calling
            )

    def vision_is_active(self) -> bool:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return not self.disable_vision and self._supports_vision()

    def _supports_vision(self) -> bool:
        """Acquire from litellm if model is vision capable.

        Returns:
            bool: True if model is vision capable. Return False if model not
                supported by litellm.
        """
        # litellm.supports_vision currently returns False for 'openai/gpt-...' or 'anthropic/claude-...' (with prefixes)  # noqa: E501
        # but model_info will have the correct value for some reason.
        # we can go with it, but we will need to keep an eye if model_info is correct for Vertex or other providers  # noqa: E501
        # remove when litellm is updated to fix https://github.com/BerriAI/litellm/issues/5608  # noqa: E501
        # Check both the full model name and the name after proxy prefix for vision support  # noqa: E501
        return (
            supports_vision(self.model)
            or supports_vision(self.model.split("/")[-1])
            or (
                self.model_info is not None
                and self.model_info.get("supports_vision", False)
            )
            or False  # fallback to False if model_info is None
        )

    def is_caching_prompt_active(self) -> bool:
        """Check if prompt caching is supported and enabled for current model.

        Returns:
            boolean: True if prompt caching is supported and enabled for the given
                model.
        """
        if not self.caching_prompt:
            return False
        # We don't need to look-up model_info, because only Anthropic models need explicit caching breakpoints  # noqa: E501
        return get_features(self.model).supports_prompt_cache

    def is_function_calling_active(self) -> bool:
        """Returns whether function calling is supported and enabled for this LLM
        instance.

        The result is cached during initialization for performance.
        """
        return self._function_calling_active

    def _post_completion(self, response: ModelResponse) -> float:
        """Post-process the completion response.

        Logs the cost and usage stats of the completion call.
        """
        try:
            cur_cost = self._completion_cost(response)
        except Exception:
            cur_cost = 0

        stats = ""
        if self.cost_metric_supported and self.metrics:
            # keep track of the cost
            stats = "Cost: %.2f USD | Accumulated Cost: %.2f USD\n" % (
                cur_cost,
                self.metrics.accumulated_cost,
            )

        # Add latency to stats if available
        if self.metrics and self.metrics.response_latencies:
            latest_latency = self.metrics.response_latencies[-1]
            stats += "Response Latency: %.3f seconds\n" % latest_latency.latency

        usage: Usage | None = response.get("usage")
        response_id = response.get("id", "unknown") or "unknown"

        if usage:
            # keep track of the input and output tokens
            prompt_tokens: int = usage.get("prompt_tokens", 0) or 0
            completion_tokens: int = usage.get("completion_tokens", 0) or 0

            if prompt_tokens:
                stats += "Input tokens: " + str(prompt_tokens)

            if completion_tokens:
                stats += (
                    (" | " if prompt_tokens else "")
                    + "Output tokens: "
                    + str(completion_tokens)
                    + "\n"
                )

            # read the prompt cache hit, if any
            prompt_tokens_details: PromptTokensDetailsWrapper | None = (
                usage.prompt_tokens_details
            )
            cache_hit_tokens = (
                prompt_tokens_details.cached_tokens
                if prompt_tokens_details and prompt_tokens_details.cached_tokens
                else 0
            )
            if cache_hit_tokens:
                stats += "Input tokens (cache hit): " + str(cache_hit_tokens) + "\n"

            # For Anthropic, the cache writes have a different cost than regular input tokens  # noqa: E501
            # but litellm doesn't separate them in the usage stats
            # we can read it from the provider-specific extra field
            model_extra = usage.get("model_extra", {})
            cache_write_tokens = (
                model_extra.get("cache_creation_input_tokens", 0) if model_extra else 0
            )
            if cache_write_tokens:
                stats += "Input tokens (cache write): " + str(cache_write_tokens) + "\n"

            # Get context window from model info
            context_window: int = 0
            if self.model_info and "max_input_tokens" in self.model_info:
                context_window = self.model_info.get("max_input_tokens") or 0
                logger.debug(f"Using context window: {context_window}")

            # Record in metrics
            # We'll treat cache_hit_tokens as "cache read" and cache_write_tokens as "cache write"  # noqa: E501
            if self.metrics:
                self.metrics.add_token_usage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cache_read_tokens=cache_hit_tokens,
                    cache_write_tokens=cache_write_tokens,
                    context_window=context_window,
                    response_id=response_id,
                )

        # log the stats
        if stats:
            logger.debug(stats)

        return cur_cost

    def get_token_count(self, messages: list[dict] | list[Message]) -> int:
        """Get the number of tokens in a list of messages. Use dicts for better
        token counting.

        Args:
            messages (list): A list of messages, either as a list of dicts or as a
                list of Message objects.

        Returns:
            int: The number of tokens.
        """
        # attempt to convert Message objects to dicts, litellm expects dicts
        if (
            isinstance(messages, list)
            and len(messages) > 0
            and isinstance(messages[0], Message)
        ):
            logger.info(
                "Message objects now include serialized tool calls in token counting"
            )
            # Assert the expected type for format_messages_for_llm
            assert isinstance(messages, list) and all(
                isinstance(m, Message) for m in messages
            ), "Expected list of Message objects"

            # We've already asserted that messages is a list of Message objects
            # Use explicit typing to satisfy mypy
            messages_typed: list[Message] = messages  # type: ignore
            messages = self.format_messages_for_llm(messages_typed)

        # try to get the token count with the default litellm tokenizers
        # or the custom tokenizer if set for this LLM configuration
        try:
            return int(
                token_counter(
                    model=self.model,
                    messages=messages,
                    custom_tokenizer=self.tokenizer,
                )
            )
        except Exception as e:
            # limit logspam in case token count is not supported
            logger.error(
                f"Error getting token count for\n model {self.model}\n{e}"
                + (
                    f"\ncustom_tokenizer: {self.custom_tokenizer}"
                    if self.custom_tokenizer is not None
                    else ""
                )
            )
            return 0

    def _is_local(self) -> bool:
        """Determines if the system is using a locally running LLM.

        Returns:
            boolean: True if executing a local model.
        """
        if self.base_url is not None:
            for substring in ["localhost", "127.0.0.1", "0.0.0.0"]:
                if substring in self.base_url:
                    return True
        elif self.model is not None:
            if self.model.startswith("ollama"):
                return True
        return False

    def _completion_cost(self, response: Any) -> float:
        """Calculate completion cost and update metrics with running total.

        Calculate the cost of a completion response based on the model. Local
        models are treated as free.
        Add the current cost into total cost in metrics.

        Args:
            response: A response from a model invocation.

        Returns:
            number: The cost of the response.
        """
        if not self.cost_metric_supported:
            return 0.0

        extra_kwargs = {}
        if (
            self.input_cost_per_token is not None
            and self.output_cost_per_token is not None
        ):
            cost_per_token = CostPerToken(
                input_cost_per_token=self.input_cost_per_token,
                output_cost_per_token=self.output_cost_per_token,
            )
            logger.debug(f"Using custom cost per token: {cost_per_token}")
            extra_kwargs["custom_cost_per_token"] = cost_per_token

        # try directly get response_cost from response
        _hidden_params = getattr(response, "_hidden_params", {})
        cost = _hidden_params.get("additional_headers", {}).get(
            "llm_provider-x-litellm-response-cost", None
        )
        if cost is not None:
            cost = float(cost)
            logger.debug(f"Got response_cost from response: {cost}")

        try:
            if cost is None:
                try:
                    cost = litellm_completion_cost(
                        completion_response=response, **extra_kwargs
                    )
                except Exception as e:
                    logger.debug(f"Error getting cost from litellm: {e}")

            if cost is None:
                _model_name = "/".join(self.model.split("/")[1:])
                cost = litellm_completion_cost(
                    completion_response=response, model=_model_name, **extra_kwargs
                )
                logger.debug(
                    f"Using fallback model name {_model_name} to get cost: {cost}"
                )
            if self.metrics:
                self.metrics.add_cost(float(cost))
            return float(cost)
        except Exception:
            object.__setattr__(self, "cost_metric_supported", False)
            logger.debug("Cost calculation not supported for this model.")
        return 0.0

    def __str__(self) -> str:
        if self.api_version:
            return f"LLM(model={self.model}, api_version={self.api_version}, base_url={self.base_url})"  # noqa: E501
        elif self.base_url:
            return f"LLM(model={self.model}, base_url={self.base_url})"
        return f"LLM(model={self.model})"

    def __repr__(self) -> str:
        return str(self)

    # TODO: we should ideally format this into a `to_litellm_message` for `Message` class`  # noqa: E501
    def format_messages_for_llm(self, messages: Message | list[Message]) -> list[dict]:
        if isinstance(messages, Message):
            messages = [messages]

        # set flags to know how to serialize the messages
        for message in messages:
            message.cache_enabled = self.is_caching_prompt_active()
            message.vision_enabled = self.vision_is_active()
            message.function_calling_enabled = self.is_function_calling_active()
            if "deepseek" in self.model:
                message.force_string_serializer = True
            if "kimi-k2-instruct" in self.model and "groq" in self.model:
                message.force_string_serializer = True
            if "openrouter/anthropic/claude-sonnet-4" in self.model:
                message.force_string_serializer = True

        # let pydantic handle the serialization
        return [message.model_dump() for message in messages]
