from __future__ import annotations

import copy
import json
import os
import warnings
from contextlib import contextmanager
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Callable,
    Literal,
    Sequence,
    Union,
    cast,
    get_args,
    get_origin,
)

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    SecretStr,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic.json_schema import SkipJsonSchema


if TYPE_CHECKING:  # type hints only, avoid runtime import cycle
    from openhands.sdk.tool.tool import ToolBase

from openhands.sdk.utils.pydantic_diff import pretty_pydantic_diff


with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import litellm

from litellm import (
    AllMessageValues,
    ChatCompletionToolParam,
    ResponseInputParam,
    completion as litellm_completion,
    responses as litellm_responses,
)
from litellm.exceptions import (
    APIConnectionError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout as LiteLLMTimeout,
)
from litellm.types.llms.openai import ResponsesAPIResponse
from litellm.types.utils import ModelResponse
from litellm.utils import (
    create_pretrained_tokenizer,
    get_model_info,
    supports_vision,
    token_counter,
)

from openhands.sdk.llm.exceptions import LLMNoResponseError
from openhands.sdk.llm.message import Message
from openhands.sdk.llm.mixins.non_native_fc import NonNativeToolCallingMixin
from openhands.sdk.llm.utils.metrics import Metrics
from openhands.sdk.llm.utils.model_features import get_features
from openhands.sdk.llm.utils.responses_converter import (
    messages_to_responses_items,
    responses_to_completion_format,
)
from openhands.sdk.llm.utils.retry_mixin import RetryMixin
from openhands.sdk.llm.utils.telemetry import Telemetry
from openhands.sdk.logger import ENV_LOG_DIR, get_logger


if TYPE_CHECKING:
    from openhands.sdk.tool import ToolBase

logger = get_logger(__name__)
CallKind = Literal["chat", "responses"]

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

# ---------------------------
# Discriminated union context
# ---------------------------


class _BaseCtxModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call_kwargs: dict[str, Any]
    log_ctx: dict[str, Any]


class ChatCtx(_BaseCtxModel):
    kind: Literal["chat"]
    messages: list[AllMessageValues]
    # tools used only in chat path
    tools: list[ChatCompletionToolParam] = Field(default_factory=list)

    # internal to support mocked tool-calls
    nonfn_msgs: list[dict[str, Any]] | None = None
    use_mock_tools: bool = False


class ResponsesCtx(_BaseCtxModel):
    kind: Literal["responses"]
    input: ResponseInputParam | str
    # tools used only in responses path
    tools: list[dict[str, Any]] = Field(default_factory=list)


ReqCtx = Annotated[Union[ChatCtx, ResponsesCtx], Field(discriminator="kind")]


class LLM(BaseModel, RetryMixin, NonNativeToolCallingMixin):
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

    num_retries: int = Field(default=5, ge=0)
    retry_multiplier: float = Field(default=8.0, ge=0)
    retry_min_wait: int = Field(default=8, ge=0)
    retry_max_wait: int = Field(default=64, ge=0)

    timeout: int | None = Field(default=None, ge=0, description="HTTP timeout (s).")

    max_message_chars: int = Field(
        default=30_000,
        ge=1,
        description="Approx max chars in each event/content sent to the LLM.",
    )

    temperature: float | None = Field(default=0.0, ge=0)
    top_p: float | None = Field(default=1.0, ge=0, le=1)
    top_k: float | None = Field(default=None, ge=0)

    custom_llm_provider: str | None = Field(default=None)
    max_input_tokens: int | None = Field(
        default=None,
        ge=1,
        description="The maximum number of input tokens. "
        "Note that this is currently unused, and the value at runtime is actually"
        " the total tokens in OpenAI (e.g. 128,000 tokens for GPT-4).",
    )
    max_output_tokens: int | None = Field(
        default=None,
        ge=1,
        description="The maximum number of output tokens. This is sent to the LLM.",
    )
    input_cost_per_token: float | None = Field(
        default=None,
        ge=0,
        description="The cost per input token. This will available in logs for user.",
    )
    output_cost_per_token: float | None = Field(
        default=None,
        ge=0,
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
    service_id: str = Field(
        default="default",
        description="Unique identifier for LLM. Typically used by LLM registry.",
    )

    # =========================================================================
    # Internal fields (excluded from dumps)
    # =========================================================================
    retry_listener: SkipJsonSchema[Callable[[int, int], None] | None] = Field(
        default=None,
        exclude=True,
    )
    _metrics: Metrics | None = PrivateAttr(default=None)
    # ===== Plain class vars (NOT Fields) =====
    # When serializing, these fields (SecretStr) will be dump to "****"
    # When deserializing, these fields will be ignored and we will override
    # them from the LLM instance provided at runtime.
    OVERRIDE_ON_SERIALIZE: tuple[str, ...] = (
        "api_key",
        "aws_access_key_id",
        "aws_secret_access_key",
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
            d["base_url"] = "https://llm-proxy.app.all-hands.dev/"

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
        if self._metrics is None:
            self._metrics = Metrics(model_name=self.model)

        self._telemetry = Telemetry(
            model_name=self.model,
            log_enabled=self.log_completions,
            log_dir=self.log_completions_folder if self.log_completions else None,
            metrics=self._metrics,
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
    # =========================================================================
    # Routing + pre-normalization helpers
    # =========================================================================
    def _select_kind(self, kwargs: dict[str, Any], tools: Any | None) -> CallKind:
        """Decide which transport to use for a completion-style request.

        - Prefer Responses API for models that support it unless explicitly forced.
        - Otherwise, use Chat Completions.
        """
        feats = get_features(self.model)
        if (
            feats.supports_responses_api
            and feats.supports_reasoning_effort
            and not kwargs.get("force_chat_completions", False)
        ):
            return "responses"
        return "chat"

    def _pre_normalize(
        self,
        *,
        kind: CallKind,
        messages: list[Message] | None,
        input: str | ResponseInputParam | None,
        tools: Sequence[ToolBase] | None,
        add_security_risk_prediction: bool = False,
    ) -> tuple[
        list[AllMessageValues] | None,
        str | ResponseInputParam | None,
        list[dict[str, Any]] | list[ChatCompletionToolParam] | None,
    ]:
        """Prepare payload for the unified request based on kind.

        Returns (messages, input, tools) normalized for the selected path.
        """
        # Local import to avoid TYPE_CHECKING branch issues
        from openhands.sdk.tool import ToolBase

        if kind == "chat":
            # Messages: ensure list[Message]
            assert messages is not None and (
                isinstance(messages, list)
                and (not messages or isinstance(messages[0], Message))
            ), "chat path expects list[Message]"
            converted_messages = self.format_messages_for_llm(
                cast(list[Message], messages)
            )

            # Tools: Tool -> ChatCompletionToolParam
            tools_cc: list[ChatCompletionToolParam] = []
            if tools:
                tools_cc = [
                    cast(ToolBase, t).to_openai_tool(
                        add_security_risk_prediction=add_security_risk_prediction
                    )
                    for t in tools
                ]  # type: ignore[arg-type]
            return converted_messages, None, tools_cc

        assert kind == "responses"
        # Input/messages handling
        if input is None:
            # If messages is None, we cannot build a request
            if messages is None:
                raise ValueError("Either messages or input must be provided")
            assert isinstance(messages, list)
            if len(messages) == 0:
                raise ValueError("messages cannot be an empty list")
            converted_messages = self.format_messages_for_llm(
                cast(list[Message], messages)
            )
            input = cast(
                ResponseInputParam, messages_to_responses_items(converted_messages)
            )
        elif isinstance(input, str):
            # pass through
            pass
        else:
            # already a typed ResponseInputParam
            pass

        # Tools: normalize to Responses tool dicts
        tools_dicts: list[dict[str, Any]] = []
        if tools:
            for t in tools:
                tools_dicts.append(
                    cast(Any, t).to_responses_tool(
                        add_security_risk_prediction=add_security_risk_prediction
                    )
                )

        return None, input, tools_dicts

    # =========================================================================
    # helpers are defined once above; this is the only definition

    # helpers are defined once above; this is the only definition

    # Routing + pre-normalization helpers

    # Serializers
    # =========================================================================
    @field_serializer(
        "api_key", "aws_access_key_id", "aws_secret_access_key", when_used="json"
    )
    def _serialize_secrets(self, v: SecretStr | None, info):
        """Serialize secret fields, exposing actual values when expose_secrets context is True."""  # noqa: E501
        if v is None:
            return None

        # Check if the 'expose_secrets' flag is in the serialization context
        if info.context and info.context.get("expose_secrets"):
            return v.get_secret_value()

        # Let Pydantic handle the default masking
        return v

    # =========================================================================
    # Public API
    # =========================================================================
    @property
    def metrics(self) -> Metrics:
        assert self._metrics is not None, (
            "Metrics should be initialized after model validation"
        )
        return self._metrics

    def completion(
        self,
        messages: list[Message],
        tools: Sequence[ToolBase] | None = None,
        return_metrics: bool = False,
        add_security_risk_prediction: bool = False,
        **kwargs,
    ) -> ModelResponse:
        """Get a completion from the LLM.

        Serialize messages/tools → (maybe) mock tools
          → normalize → transport → postprocess.
        """
        if kwargs.get("stream", False):
            raise ValueError("Streaming is not supported")

        # Decide route once, then pre-normalize for unified engine
        kind = self._select_kind(kwargs, tools)
        msgs, inp, ttools = self._pre_normalize(
            kind=kind,
            messages=messages,
            input=None,
            tools=tools,
            add_security_risk_prediction=add_security_risk_prediction,
        )
        return self._unified_request(
            kind=kind,
            messages=msgs,
            input=inp,
            tools=ttools,
            **kwargs,
        )

    def responses(
        self,
        messages: list[Message] | str | None = None,
        input: str | ResponseInputParam | None = None,
        tools: Sequence[ToolBase] | None = None,
        add_security_risk_prediction: bool = False,
        **kwargs,
    ) -> ModelResponse:
        if not get_features(self.model).supports_responses_api:
            raise ValueError(
                f"Model {self.model} does not support the Responses API. "
                f"Use completion() method instead."
            )
        if kwargs.get("stream", False):
            raise ValueError("Streaming is not supported in responses() method")

        # Normalize simple string messages to input
        if isinstance(messages, str) and input is None:
            input = messages
            messages = None
        # Guard: require either messages or input
        if messages is None and input is None:
            raise ValueError("Either messages or input must be provided")

        # Use unified pre-normalization for responses
        msgs, inp, tools_dicts = self._pre_normalize(
            kind="responses",
            messages=cast(list[Message] | None, messages),
            input=input,
            tools=tools,
            add_security_risk_prediction=add_security_risk_prediction,
        )

        return self._unified_request(
            kind="responses",
            messages=msgs,
            input=inp,
            tools=cast(
                list[dict[str, Any]] | list[ChatCompletionToolParam] | None, tools_dicts
            ),
            **kwargs,
        )

    # ---------------------------
    # Unified engine
    # ---------------------------

    def _unified_request(
        self,
        *,
        kind: CallKind,
        messages: list[AllMessageValues] | None = None,
        input: str | ResponseInputParam | None = None,
        tools: list[dict[str, Any]] | list[ChatCompletionToolParam] | None = None,
        **kwargs,
    ) -> ModelResponse:
        assert self._telemetry is not None

        kwargs["tools"] = tools  # might be removed in _normalize_kwargs

        # 1) Build validated context (Pydantic will enforce required fields by kind)
        ctx: ReqCtx = self._build_ctx(
            kind=kind,
            messages=messages,
            input=input,
            tools=tools or [],
            opts=kwargs,
        )

        # 2) Telemetry (request)
        self._telemetry.on_request(log_ctx=ctx.log_ctx)

        # 3) Retry wrapper
        @self.retry_decorator(
            num_retries=self.num_retries,
            retry_exceptions=LLM_RETRY_EXCEPTIONS,
            retry_min_wait=self.retry_min_wait,
            retry_max_wait=self.retry_max_wait,
            retry_multiplier=self.retry_multiplier,
            retry_listener=self.retry_listener,
        )
        def _one_attempt(**_tenacity_kwargs: Any) -> ModelResponse:
            # Transport
            resp = self._transport_dispatch(ctx)

            # Post-process + telemetry (response)
            resp = self._postprocess_dispatch(ctx, resp)

            # Response invariant
            if not resp.choices or len(resp.choices) < 1:
                raise LLMNoResponseError(
                    "Response choices is less than 1. Response: " + str(resp)
                )
            return resp

        try:
            return _one_attempt()
        except Exception as e:
            self._telemetry.on_error(e)
            raise

    # ---------------------------
    # Build + normalize once
    # ---------------------------

    def _build_ctx(
        self,
        *,
        kind: CallKind,
        messages: list[AllMessageValues] | None,
        input: str | ResponseInputParam | None,
        tools: list[dict[str, Any]] | list[ChatCompletionToolParam] | None,
        opts: dict[str, Any],
    ) -> ReqCtx:
        # Mock tools for non-native function-calling
        nonfn_msgs: list[dict[str, Any]] | None = None
        use_mock_tools = False
        if kind == "chat":
            use_mock_tools = self.should_mock_tool_calls(
                cast(list[ChatCompletionToolParam] | None, tools)
            )
        if kind == "chat" and use_mock_tools:
            logger.debug(
                "LLM.completion: mocking function-calling via prompt "
                f"for model {self.model}"
            )

            # When mocking, we need raw dict messages; convert AllMessageValues to dict
            def _to_raw_dict(x: AllMessageValues | dict[str, Any]) -> dict[str, Any]:
                if isinstance(x, dict):
                    return cast(dict[str, Any], x)
                # x is a Pydantic message model; convert to dict
                return cast(dict[str, Any], cast(Any, x).model_dump())

            raw_msgs: list[dict[str, Any]] = [_to_raw_dict(m) for m in (messages or [])]
            nonfn_msgs, opts = self.pre_request_prompt_mock(
                raw_msgs, cast(list[ChatCompletionToolParam], tools) or [], opts
            )

        has_tools = bool(tools) and (kind == "chat") and not use_mock_tools
        call_kwargs = self._normalize_kwargs(kind, opts, has_tools=has_tools)

        # Build log context (what we write is exactly what we send)
        log_ctx: dict[str, Any] = {
            "kind": kind,
            "kwargs": {k: v for k, v in call_kwargs.items()},
            "context_window": self.max_input_tokens or 0,
        }

        # Build the request context
        if kind == "chat":
            log_ctx["messages"] = (messages or [])[:]
            log_ctx["tools"] = tools if has_tools else None
            if nonfn_msgs is not None:
                log_ctx["raw_messages"] = nonfn_msgs
            return ChatCtx(
                kind="chat",
                messages=messages or [],
                nonfn_msgs=nonfn_msgs,
                use_mock_tools=use_mock_tools,
                call_kwargs=call_kwargs,
                log_ctx=log_ctx,
                tools=cast(list[ChatCompletionToolParam], tools or []),
            )
        else:
            log_ctx["input"] = input if input is not None else []
            return ResponsesCtx(
                kind="responses",
                input=cast(ResponseInputParam | str, input or []),
                call_kwargs=call_kwargs,
                log_ctx=log_ctx,
                tools=cast(list[dict[str, Any]], tools or []),
            )

    def _normalize_kwargs(self, kind: CallKind, opts: dict, *, has_tools: bool) -> dict:
        out = dict(opts)

        # Respect configured sampling params unless reasoning models override
        if self.top_k is not None:
            out.setdefault("top_k", self.top_k)
        if self.top_p is not None:
            out.setdefault("top_p", self.top_p)
        if self.temperature is not None:
            out.setdefault("temperature", self.temperature)

        # Max tokens (chat vs responses)
        if kind == "chat":
            if self.max_output_tokens is not None:
                out.setdefault("max_completion_tokens", self.max_output_tokens)
            if self.model.startswith("azure") and "max_completion_tokens" in out:
                out["max_tokens"] = out.pop("max_completion_tokens")
        else:
            if self.max_output_tokens is not None:
                out.setdefault("max_output_tokens", self.max_output_tokens)

        # Reasoning-model quirks
        if get_features(self.model).supports_reasoning_effort:
            # Only include top-level reasoning_effort for chat.
            # Responses API uses reasoning.effort
            if kind == "chat" and self.reasoning_effort is not None:
                out["reasoning_effort"] = (
                    self.reasoning_effort
                    if self.reasoning_effort not in (None, "none")
                    else "low"
                )
            out.pop("temperature", None)
            out.pop("top_p", None)

        # Anthropic Opus 4.1: prefer temperature when
        # both provided; disable extended thinking
        if "claude-opus-4-1" in self.model.lower():
            if "temperature" in out and "top_p" in out:
                out.pop("top_p", None)
            out.setdefault("thinking", {"type": "disabled"})

        # Responses API specific!
        if kind == "responses":
            effort_val = None
            if get_features(self.model).supports_reasoning_effort:
                if self.reasoning_effort not in (None, "none"):
                    effort_val = self.reasoning_effort
                else:
                    effort_val = "low"
            if effort_val is not None:
                out.setdefault(
                    "reasoning",
                    {"effort": effort_val, "summary": "detailed"},
                )
            out.pop("reasoning_effort", None)
            out.setdefault("store", True)

        # Mistral / Gemini safety
        if self.safety_settings:
            ml = self.model.lower()
            if "mistral" in ml or "gemini" in ml:
                out["safety_settings"] = self.safety_settings

        # Tools in Chat Completions only when native FC is active.
        # Do not drop tools for Responses API; they are supported there.
        if kind == "chat" and not has_tools:
            out.pop("tools", None)
            out.pop("tool_choice", None)

        # Responses API doesn't support stop/tools
        if kind == "responses":
            out.pop("stop", None)

        # Only keep extra_body for litellm_proxy
        if "litellm_proxy" not in self.model:
            out.pop("extra_body", None)

        return out

    # ---------------------------
    # Transport + postprocess
    # ---------------------------

    def _transport_dispatch(self, ctx: ReqCtx) -> ModelResponse:
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
                warnings.filterwarnings(
                    "ignore",
                    message=r"There is no current event loop",
                    category=DeprecationWarning,
                )

                if ctx.kind == "chat":
                    ret = litellm_completion(
                        model=self.model,
                        api_key=self.api_key.get_secret_value()
                        if self.api_key
                        else None,
                        base_url=self.base_url,
                        api_version=self.api_version,
                        timeout=self.timeout,
                        drop_params=self.drop_params,
                        seed=self.seed,
                        messages=ctx.messages,
                        **ctx.call_kwargs,
                    )
                    assert isinstance(ret, ModelResponse)
                    return ret
                else:
                    raw = litellm_responses(
                        model=self.model,
                        api_key=self.api_key.get_secret_value()
                        if self.api_key
                        else None,
                        base_url=self.base_url,
                        api_base=self.base_url,
                        api_version=self.api_version,
                        timeout=self.timeout,
                        input=ctx.input,
                        drop_params=self.drop_params,
                        custom_llm_provider=(
                            self.model.split("/")[1]
                            if self.model.startswith("litellm_proxy/")
                            else None
                        ),
                        stream=False,  # enforce non-stream for typed converter
                        **ctx.call_kwargs,
                    )
                    return responses_to_completion_format(
                        cast(ResponsesAPIResponse, raw)
                    )

    def _postprocess_dispatch(self, ctx: ReqCtx, resp: ModelResponse) -> ModelResponse:
        assert self._telemetry is not None
        # tool-mocking only applies to chat when we mocked pre-request
        if ctx.kind == "chat" and getattr(ctx, "use_mock_tools", False):  # type: ignore[attr-defined]
            raw_resp = copy.deepcopy(resp)
            resp = self.post_response_prompt_mock(
                resp,
                nonfncall_msgs=getattr(ctx, "nonfn_msgs") or [],  # type: ignore[attr-defined]
                tools=ctx.tools,
            )
            # keep raw vs converted for telemetry parity
            self._telemetry.on_response(resp, raw_resp=raw_resp)
            return resp
        self._telemetry.on_response(resp)
        return resp

    # =========================================================================
    # Helpers
    # =========================================================================

    @contextmanager
    def _litellm_modify_params_ctx(self, flag: bool):
        old = getattr(litellm, "modify_params", None)
        try:
            litellm.modify_params = flag
            yield
        finally:
            litellm.modify_params = old

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

    def is_responses_api_supported(self) -> bool:
        """Returns whether Responses API is supported for this model."""
        return get_features(self.model).supports_responses_api

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

    def format_messages_for_llm(
        self, messages: list[Message]
    ) -> list[AllMessageValues]:
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

    def get_token_count(self, messages: list[Message]) -> int:
        logger.info(
            "Message objects now include serialized tool calls in token counting"
        )
        formatted_messages = self.format_messages_for_llm(messages)
        try:
            return int(
                token_counter(
                    model=self.model,
                    messages=formatted_messages,
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
        """Serialize the LLM instance to a dictionary."""
        return self.model_dump()

    def store_to_json(self, filepath: str) -> None:
        """Store the LLM instance to a JSON file with secrets exposed.

        Args:
            filepath: Path where the JSON file should be stored.
        """
        data = self.model_dump_with_secrets()

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

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

    def resolve_diff_from_deserialized(self, persisted: "LLM") -> "LLM":
        """Resolve differences between a deserialized LLM and the current instance.

        This is due to fields like api_key being serialized to "****" in dumps,
        and we want to ensure that when loading from a file, we still use the
        runtime-provided api_key in the self instance.

        Return a new LLM instance equivalent to `persisted` but with
        explicitly whitelisted fields (e.g. api_key) taken from `self`.
        """
        if persisted.__class__ is not self.__class__:
            raise ValueError(
                f"Cannot resolve_diff_from_deserialized between {self.__class__} "
                f"and {persisted.__class__}"
            )

        # Copy allowed fields from runtime llm into the persisted llm
        llm_updates = {}
        persisted_dump = persisted.model_dump(exclude_none=True)
        for field in self.OVERRIDE_ON_SERIALIZE:
            if field in persisted_dump.keys():
                llm_updates[field] = getattr(self, field)
        if llm_updates:
            reconciled = persisted.model_copy(update=llm_updates)
        else:
            reconciled = persisted

        if self.model_dump(exclude_none=True) != reconciled.model_dump(
            exclude_none=True
        ):
            raise ValueError(
                "The LLM provided is different from the one in persisted state.\n"
                f"Diff: {pretty_pydantic_diff(self, reconciled)}"
            )
        return reconciled

    def model_dump_with_secrets(self) -> dict[str, Any]:
        """Dump the model including secrets (normally excluded)."""
        data = self.model_dump()
        for field in self.OVERRIDE_ON_SERIALIZE:
            attr = getattr(self, field)
            if attr is not None and isinstance(attr, SecretStr):
                data[field] = attr.get_secret_value()
        return data
