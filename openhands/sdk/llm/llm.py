import copy
import json
import os
import time
import warnings
from contextlib import contextmanager
from typing import Any, Callable, Literal, TypeGuard, cast, get_args, get_origin

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    SecretStr,
    field_validator,
    model_validator,
)


with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import litellm

from litellm import (
    ChatCompletionToolParam,
    Message as LiteLLMMessage,
    completion as litellm_completion,
)
from litellm.exceptions import (
    APIConnectionError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout as LiteLLMTimeout,
)
from litellm.types.utils import (
    Choices,
    ModelResponse,
    StreamingChoices,
)
from litellm.utils import (
    create_pretrained_tokenizer,
    get_model_info,
    supports_vision,
    token_counter,
)

# OpenHands utilities
from openhands.sdk.llm.exceptions import LLMNoResponseError
from openhands.sdk.llm.message import Message
from openhands.sdk.llm.utils.fn_call_converter import (
    STOP_WORDS,
    convert_fncall_messages_to_non_fncall_messages,
    convert_non_fncall_messages_to_fncall_messages,
)
from openhands.sdk.llm.utils.metrics import Metrics
from openhands.sdk.llm.utils.model_features import get_features
from openhands.sdk.llm.utils.telemetry import Telemetry
from openhands.sdk.logger import ENV_LOG_DIR, get_logger


logger = get_logger(__name__)

__all__ = ["LLM"]

# Exceptions we retry on
LLM_RETRY_EXCEPTIONS: tuple[type[Exception], ...] = (
    APIConnectionError,
    RateLimitError,
    ServiceUnavailableError,
    LiteLLMTimeout,
    InternalServerError,
    LLMNoResponseError,
)


class RetryMixin:
    """Minimal retry mixin kept from your original design."""

    def retry_decorator(
        self,
        *,
        num_retries: int,
        retry_exceptions: tuple[type[Exception], ...],
        retry_min_wait: int,
        retry_max_wait: int,
        retry_multiplier: float,
        retry_listener: Callable[[int, int], None] | None = None,
    ):
        def decorator(fn: Callable[[], Any]):
            def wrapped():
                import random

                attempt = 0
                wait = retry_min_wait
                last_exc = None
                while attempt < num_retries:
                    try:
                        return fn()
                    except retry_exceptions as e:
                        last_exc = e
                        if attempt == num_retries - 1:
                            break
                        # jittered exponential backoff
                        sleep_for = min(
                            retry_max_wait, int(wait + random.uniform(0, 1))
                        )
                        if retry_listener:
                            retry_listener(attempt + 1, num_retries)
                        time.sleep(sleep_for)
                        wait = max(retry_min_wait, int(wait * retry_multiplier))
                        attempt += 1
                assert last_exc is not None
                raise last_exc

            return wrapped

        return decorator


class LLM(BaseModel, RetryMixin):
    """Refactored LLM: simple `completion()`, centralized Telemetry, tiny helpers."""

    # =========================================================================
    # Config fields
    # =========================================================================
    model: str = Field(default="claude-sonnet-4-20250514", description="Model name.")
    api_key: SecretStr | None = Field(default=None, description="API key.")
    base_url: str | None = Field(default=None, description="Custom base URL.")
    api_version: str | None = Field(
        default=None, description="API version (e.g., Azure)."
    )

    aws_access_key_id: SecretStr | None = Field(default=None)
    aws_secret_access_key: SecretStr | None = Field(default=None)
    aws_region_name: str | None = Field(default=None)

    openrouter_site_url: str = Field(default="https://docs.all-hands.dev/")
    openrouter_app_name: str = Field(default="OpenHands")

    num_retries: int = Field(default=5)
    retry_multiplier: float = Field(default=8)
    retry_min_wait: int = Field(default=8)
    retry_max_wait: int = Field(default=64)

    timeout: int | None = Field(default=None, description="HTTP timeout (s).")

    max_message_chars: int = Field(
        default=30_000,
        description="Approx max chars in each event/content sent to the LLM.",
    )

    temperature: float | None = Field(default=0.0)
    top_p: float | None = Field(default=1.0)
    top_k: float | None = Field(default=None)

    custom_llm_provider: str | None = Field(default=None)
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
    ollama_base_url: str | None = Field(default=None)

    drop_params: bool = Field(default=True)
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

    # =========================================================================
    # Internal fields (excluded from dumps)
    # =========================================================================
    service_id: str = Field(default="default", exclude=True)
    metrics: Metrics | None = Field(default=None, exclude=True)
    retry_listener: Callable[[int, int], None] | None = Field(
        default=None, exclude=True
    )

    # Runtime-only private attrs
    _model_info: Any = PrivateAttr(default=None)
    _tokenizer: Any = PrivateAttr(default=None)
    _function_calling_active: bool = PrivateAttr(default=False)
    _telemetry: Telemetry | None = PrivateAttr(default=None)

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    # =========================================================================
    # Validators
    # =========================================================================
    @field_validator("api_key", mode="before")
    @classmethod
    def _validate_api_key(cls, v):
        """Convert empty API keys to None to allow boto3 to use alternative auth methods."""  # noqa: E501
        if v is None:
            return None

        # Handle both SecretStr and string inputs
        if isinstance(v, SecretStr):
            secret_value = v.get_secret_value()
        else:
            secret_value = str(v)

        # If the API key is empty or whitespace-only, return None
        if not secret_value or not secret_value.strip():
            return None

        return v

    @model_validator(mode="before")
    @classmethod
    def _coerce_inputs(cls, data):
        if not isinstance(data, dict):
            return data
        d = dict(data)

        model_val = d.get("model")
        if not model_val:
            raise ValueError("model must be specified in LLM")

        # default reasoning_effort unless Gemini 2.5
        # (we keep consistent with old behavior)
        if d.get("reasoning_effort") is None and "gemini-2.5-pro" not in model_val:
            d["reasoning_effort"] = "high"

        # Azure default version
        if model_val.startswith("azure") and not d.get("api_version"):
            d["api_version"] = "2024-12-01-preview"

        # Provider rewrite: openhands/* -> litellm_proxy/*
        if model_val.startswith("openhands/"):
            model_name = model_val.removeprefix("openhands/")
            d["model"] = f"litellm_proxy/{model_name}"
            d.setdefault("base_url", "https://llm-proxy.app.all-hands.dev/")

        # HF doesn't support the OpenAI default value for top_p (1)
        if model_val.startswith("huggingface"):
            if d.get("top_p", 1.0) == 1.0:
                d["top_p"] = 0.9

        return d

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

        # Metrics + Telemetry wiring
        if self.metrics is None:
            self.metrics = Metrics(model_name=self.model)

        self._telemetry = Telemetry(
            model_name=self.model,
            log_enabled=self.log_completions,
            log_dir=self.log_completions_folder if self.log_completions else None,
            metrics=self.metrics,
        )

        # Tokenizer
        if self.custom_tokenizer:
            self._tokenizer = create_pretrained_tokenizer(self.custom_tokenizer)

        # Capabilities + model info
        self._init_model_info_and_caps()

        logger.debug(
            f"LLM ready: model={self.model} base_url={self.base_url} "
            f"reasoning_effort={self.reasoning_effort}"
        )
        return self

    # =========================================================================
    # Public API
    # =========================================================================
    def completion(
        self,
        messages: list[dict[str, Any]] | list[Message],
        tools: list[ChatCompletionToolParam] | None = None,
        return_metrics: bool = False,
        **kwargs,
    ) -> ModelResponse:
        """Single entry point for LLM completion.

        Normalize → (maybe) mock tools → transport → postprocess.
        """
        # Check if streaming is requested
        if kwargs.get("stream", False):
            raise ValueError("Streaming is not supported")

        # 1) serialize messages
        if messages and isinstance(messages[0], Message):
            messages = self.format_messages_for_llm(cast(list[Message], messages))
        else:
            messages = cast(list[dict[str, Any]], messages)

        # 2) choose function-calling strategy
        use_native_fc = self.is_function_calling_active()
        original_fncall_msgs = copy.deepcopy(messages)
        if tools and not use_native_fc:
            logger.debug(
                "LLM.completion: mocking function-calling via prompt "
                f"for model {self.model}"
            )
            messages, kwargs = self._pre_request_prompt_mock(messages, tools, kwargs)

        # 3) normalize provider params
        kwargs["tools"] = tools  # we might remove this field in _normalize_call_kwargs
        has_tools_flag = (
            bool(tools) and use_native_fc
        )  # only keep tools when native FC is active
        call_kwargs = self._normalize_call_kwargs(kwargs, has_tools=has_tools_flag)

        # 4) optional request logging context (kept small)
        assert self._telemetry is not None
        log_ctx = None
        if self._telemetry.log_enabled:
            log_ctx = {
                "messages": messages[:],  # already simple dicts
                "tools": tools,
                "kwargs": {k: v for k, v in call_kwargs.items()},
                "context_window": self.max_input_tokens,
            }
            if tools and not use_native_fc:
                log_ctx["raw_messages"] = original_fncall_msgs
        self._telemetry.on_request(log_ctx=log_ctx)

        # 5) do the call with retries
        @self.retry_decorator(
            num_retries=self.num_retries,
            retry_exceptions=LLM_RETRY_EXCEPTIONS,
            retry_min_wait=self.retry_min_wait,
            retry_max_wait=self.retry_max_wait,
            retry_multiplier=self.retry_multiplier,
            retry_listener=self.retry_listener,
        )
        def _one_attempt() -> ModelResponse:
            assert self._telemetry is not None
            resp = self._transport_call(messages=messages, **call_kwargs)
            raw_resp: ModelResponse | None = None
            if tools and not use_native_fc:
                raw_resp = copy.deepcopy(resp)
                resp = self._post_response_prompt_mock(
                    resp, nonfncall_msgs=messages, tools=tools
                )
            # 6) telemetry
            self._telemetry.on_response(resp, raw_resp=raw_resp)

            # Ensure at least one choice
            if not resp.get("choices") or len(resp["choices"]) < 1:
                raise LLMNoResponseError(
                    "Response choices is less than 1. Response: " + str(resp)
                )

            return resp

        try:
            resp = _one_attempt()
            return resp
        except Exception as e:
            self._telemetry.on_error(e)
            raise

    # =========================================================================
    # Transport + helpers
    # =========================================================================
    def _transport_call(
        self, *, messages: list[dict[str, Any]], **kwargs
    ) -> ModelResponse:
        # litellm.modify_params is GLOBAL; guard it for thread-safety
        with self._litellm_modify_params_ctx(self.modify_params):
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", category=DeprecationWarning, module="httpx.*"
                )
                warnings.filterwarnings(
                    "ignore",
                    message=r".*content=.*upload.*",
                    category=DeprecationWarning,
                )
                # Some providers need renames handled in _normalize_call_kwargs.
                ret = litellm_completion(
                    model=self.model,
                    api_key=self.api_key.get_secret_value() if self.api_key else None,
                    base_url=self.base_url,
                    api_version=self.api_version,
                    timeout=self.timeout,
                    drop_params=self.drop_params,
                    seed=self.seed,
                    messages=messages,
                    **kwargs,
                )
                assert isinstance(ret, ModelResponse), (
                    f"Expected ModelResponse, got {type(ret)}"
                )
                return ret

    @contextmanager
    def _litellm_modify_params_ctx(self, flag: bool):
        old = getattr(litellm, "modify_params", None)
        try:
            litellm.modify_params = flag
            yield
        finally:
            litellm.modify_params = old

    def _normalize_call_kwargs(self, opts: dict, *, has_tools: bool) -> dict:
        """Central place for provider quirks + param harmonization."""
        out = dict(opts)

        # Respect configured sampling params unless reasoning models override
        if self.top_k is not None:
            out.setdefault("top_k", self.top_k)
        if self.top_p is not None:
            out.setdefault("top_p", self.top_p)
        if self.temperature is not None:
            out.setdefault("temperature", self.temperature)

        # Max tokens wiring differences
        if self.max_output_tokens is not None:
            # OpenAI-compatible param is `max_completion_tokens`
            out.setdefault("max_completion_tokens", self.max_output_tokens)

        # Azure -> uses max_tokens instead
        if self.model.startswith("azure"):
            if "max_completion_tokens" in out:
                out["max_tokens"] = out.pop("max_completion_tokens")

        # Reasoning-model quirks
        if get_features(self.model).supports_reasoning_effort:
            # Preferred: use reasoning_effort
            if self.reasoning_effort is not None:
                out["reasoning_effort"] = self.reasoning_effort
            # Anthropic/OpenAI reasoning models ignore temp/top_p
            out.pop("temperature", None)
            out.pop("top_p", None)
            # Gemini 2.5-pro default to low if not set
            # otherwise litellm doesn't send reasoning, even though it happens
            if "gemini-2.5-pro" in self.model:
                if self.reasoning_effort in {None, "none"}:
                    out["reasoning_effort"] = "low"

        # Anthropic Opus 4.1: prefer temperature when
        # both provided; disable extended thinking
        if "claude-opus-4-1" in self.model.lower():
            if "temperature" in out and "top_p" in out:
                out.pop("top_p", None)
            out.setdefault("thinking", {"type": "disabled"})

        # Mistral / Gemini safety
        if self.safety_settings:
            ml = self.model.lower()
            if "mistral" in ml or "gemini" in ml:
                out["safety_settings"] = self.safety_settings

        # Tools: if not using native, strip tool_choice so we don't confuse providers
        if not has_tools:
            out.pop("tools", None)
            out.pop("tool_choice", None)

        # non litellm proxy special-case: keep `extra_body` off unless model requires it
        if "litellm_proxy" not in self.model:
            out.pop("extra_body", None)

        return out

    def _pre_request_prompt_mock(
        self, messages: list[dict], tools: list[ChatCompletionToolParam], kwargs: dict
    ) -> tuple[list[dict], dict]:
        """Convert to non-fncall prompting when native tool-calling is off."""
        add_iclex = not any(s in self.model for s in ("openhands-lm", "devstral"))
        messages = convert_fncall_messages_to_non_fncall_messages(
            messages, tools, add_in_context_learning_example=add_iclex
        )
        if get_features(self.model).supports_stop_words and not self.disable_stop_word:
            kwargs = dict(kwargs)
            kwargs["stop"] = STOP_WORDS

        # Ensure we don't send tool_choice when mocking
        kwargs.pop("tool_choice", None)
        return messages, kwargs

    def _post_response_prompt_mock(
        self,
        resp: ModelResponse,
        nonfncall_msgs: list[dict],
        tools: list[ChatCompletionToolParam],
    ) -> ModelResponse:
        if len(resp.choices) < 1:
            raise LLMNoResponseError(
                "Response choices is less than 1 (seen in some providers). Resp: "
                + str(resp)
            )

        def _all_choices(
            items: list[Choices | StreamingChoices],
        ) -> TypeGuard[list[Choices]]:
            return all(isinstance(c, Choices) for c in items)

        if not _all_choices(resp.choices):
            raise AssertionError(
                "Expected non-streaming Choices when post-processing mocked tools"
            )

        # Preserve provider-specific reasoning fields before conversion
        orig_msg = resp.choices[0].message
        non_fn_message: dict = orig_msg.model_dump()
        fn_msgs: list[dict] = convert_non_fncall_messages_to_fncall_messages(
            nonfncall_msgs + [non_fn_message], tools
        )
        last: dict = fn_msgs[-1]

        for name in ("reasoning_content", "provider_specific_fields"):
            val = getattr(orig_msg, name, None)
            if not val:
                continue
            last[name] = val

        resp.choices[0].message = LiteLLMMessage.model_validate(last)
        return resp

    # =========================================================================
    # Capabilities, formatting, and info
    # =========================================================================
    def _init_model_info_and_caps(self) -> None:
        # Try to get model info via openrouter or litellm proxy first
        tried = False
        try:
            if self.model.startswith("openrouter"):
                self._model_info = get_model_info(self.model)
                tried = True
        except Exception as e:
            logger.debug(f"get_model_info(openrouter) failed: {e}")

        if not tried and self.model.startswith("litellm_proxy/"):
            # IF we are using LiteLLM proxy, get model info from LiteLLM proxy
            # GET {base_url}/v1/model/info with litellm_model_id as path param
            base_url = self.base_url.strip() if self.base_url else ""
            if not base_url.startswith(("http://", "https://")):
                base_url = "http://" + base_url
            try:
                api_key = self.api_key.get_secret_value() if self.api_key else ""
                response = httpx.get(
                    f"{base_url}/v1/model/info",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                data = response.json().get("data", [])
                current = next(
                    (
                        info
                        for info in data
                        if info["model_name"]
                        == self.model.removeprefix("litellm_proxy/")
                    ),
                    None,
                )
                if current:
                    self._model_info = current.get("model_info")
                    logger.debug(
                        f"Got model info from litellm proxy: {self._model_info}"
                    )
            except Exception as e:
                logger.info(f"Error fetching model info from proxy: {e}")

        # Fallbacks: try base name variants
        if not self._model_info:
            try:
                self._model_info = get_model_info(self.model.split(":")[0])
            except Exception:
                pass
        if not self._model_info:
            try:
                self._model_info = get_model_info(self.model.split("/")[-1])
            except Exception:
                pass

        # Context window and max_output_tokens
        if (
            self.max_input_tokens is None
            and self._model_info is not None
            and isinstance(self._model_info.get("max_input_tokens"), int)
        ):
            self.max_input_tokens = self._model_info.get("max_input_tokens")

        if self.max_output_tokens is None:
            if any(m in self.model for m in ["claude-3-7-sonnet", "claude-3.7-sonnet"]):
                self.max_output_tokens = (
                    64000  # practical cap (litellm may allow 128k with header)
                )
            elif self._model_info is not None:
                if isinstance(self._model_info.get("max_output_tokens"), int):
                    self.max_output_tokens = self._model_info.get("max_output_tokens")
                elif isinstance(self._model_info.get("max_tokens"), int):
                    self.max_output_tokens = self._model_info.get("max_tokens")

        # Function-calling capabilities
        feats = get_features(self.model)
        logger.info(f"Model features for {self.model}: {feats}")
        self._function_calling_active = (
            self.native_tool_calling
            if self.native_tool_calling is not None
            else feats.supports_function_calling
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
                self._model_info is not None
                and self._model_info.get("supports_vision", False)
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
        # We don't need to look-up model_info, because
        # only Anthropic models need explicit caching breakpoints
        return self.caching_prompt and get_features(self.model).supports_prompt_cache

    def is_function_calling_active(self) -> bool:
        """Returns whether function calling is supported
        and enabled for this LLM instance.
        """
        return bool(self._function_calling_active)

    @property
    def model_info(self) -> dict | None:
        """Returns the model info dictionary."""
        return self._model_info

    # =========================================================================
    # Utilities preserved from previous class
    # =========================================================================
    def _apply_prompt_caching(self, messages: list[Message]) -> None:
        """Applies caching breakpoints to the messages.

        For new Anthropic API, we only need to mark the last user or
          tool message as cacheable.
        """
        if len(messages) > 0 and messages[0].role == "system":
            messages[0].content[-1].cache_prompt = True
        # NOTE: this is only needed for anthropic
        for message in reversed(messages):
            if message.role in ("user", "tool"):
                message.content[
                    -1
                ].cache_prompt = True  # Last item inside the message content
                break

    def format_messages_for_llm(self, messages: list[Message]) -> list[dict]:
        """Formats Message objects for LLM consumption."""

        messages = copy.deepcopy(messages)
        if self.is_caching_prompt_active():
            self._apply_prompt_caching(messages)

        for message in messages:
            message.cache_enabled = self.is_caching_prompt_active()
            message.vision_enabled = self.vision_is_active()
            message.function_calling_enabled = self.is_function_calling_active()
            if "deepseek" in self.model or (
                "kimi-k2-instruct" in self.model and "groq" in self.model
            ):
                message.force_string_serializer = True

        return [message.to_llm_dict() for message in messages]

    def get_token_count(self, messages: list[dict] | list[Message]) -> int:
        if isinstance(messages, list) and messages and isinstance(messages[0], Message):
            logger.info(
                "Message objects now include serialized tool calls in token counting"
            )
            messages = self.format_messages_for_llm(cast(list[Message], messages))
        try:
            return int(
                token_counter(
                    model=self.model,
                    messages=messages,  # type: ignore[arg-type]
                    custom_tokenizer=self._tokenizer,
                )
            )
        except Exception as e:
            logger.error(
                f"Error getting token count for model {self.model}\n{e}"
                + (
                    f"\ncustom_tokenizer: {self.custom_tokenizer}"
                    if self.custom_tokenizer
                    else ""
                ),
                exc_info=True,
            )
            return 0

    # =========================================================================
    # Serialization helpers
    # =========================================================================
    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "LLM":
        return cls(**data)

    def serialize(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def load_from_json(cls, json_path: str) -> "LLM":
        with open(json_path, "r") as f:
            data = json.load(f)
        return cls.deserialize(data)

    @classmethod
    def load_from_env(cls, prefix: str = "LLM_") -> "LLM":
        TRUTHY = {"true", "1", "yes", "on"}

        def _unwrap_type(t: Any) -> Any:
            origin = get_origin(t)
            if origin is None:
                return t
            args = [a for a in get_args(t) if a is not type(None)]
            return args[0] if args else t

        def _cast_value(raw: str, t: Any) -> Any:
            t = _unwrap_type(t)
            if t is SecretStr:
                return SecretStr(raw)
            if t is bool:
                return raw.lower() in TRUTHY
            if t is int:
                try:
                    return int(raw)
                except ValueError:
                    return None
            if t is float:
                try:
                    return float(raw)
                except ValueError:
                    return None
            origin = get_origin(t)
            if (origin in (list, dict, tuple)) or (
                isinstance(t, type) and issubclass(t, BaseModel)
            ):
                try:
                    return json.loads(raw)
                except Exception:
                    pass
            return raw

        data: dict[str, Any] = {}
        fields: dict[str, Any] = {
            name: f.annotation
            for name, f in cls.model_fields.items()
            if not getattr(f, "exclude", False)
        }

        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            field_name = key[len(prefix) :].lower()
            if field_name not in fields:
                continue
            v = _cast_value(value, fields[field_name])
            if v is not None:
                data[field_name] = v
        return cls.deserialize(data)

    @classmethod
    def load_from_toml(cls, toml_path: str) -> "LLM":
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore
            except ImportError:
                raise ImportError("tomllib or tomli is required to load TOML files")
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
        if "llm" in data:
            data = data["llm"]
        return cls.deserialize(data)
