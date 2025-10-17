import json
import os
import time
import uuid
import warnings
from dataclasses import dataclass, field, InitVar
from typing import Any

from litellm.cost_calculator import completion_cost as litellm_completion_cost
from litellm.types.llms.openai import ResponseAPIUsage, ResponsesAPIResponse
from litellm.types.utils import CostPerToken, ModelResponse, Usage

from openhands.sdk.llm.utils.metrics import Metrics
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


@dataclass(eq=True)
class Telemetry:
    """
    Boring, simple telemetry service.
    - Dataclass for stable value-equality on config fields
    - Records latency, token usage, cost into provided Metrics
    - Optional JSON log writing
    """

    # External dependency, excluded from equality (identity, runtime-managed)
    metrics: InitVar[Metrics | None] = None
    _metrics: Metrics = field(init=False, compare=False, repr=False)

    # Config fields (participate in equality)
    model_name: str = "unknown"
    log_enabled: bool = False
    log_dir: str | None = None
    input_cost_per_token: float | None = None
    output_cost_per_token: float | None = None

    # Runtime state: excluded from equality and initialization
    _req_start: float = field(default=0.0, init=False, compare=False, repr=False)
    _req_ctx: dict[str, Any] = field(
        default_factory=dict, init=False, compare=False, repr=False
    )
    _last_latency: float = field(default=0.0, init=False, compare=False, repr=False)

    def __post_init__(self, metrics: Metrics | None) -> None:
        if not isinstance(metrics, Metrics):
            raise ValueError("Telemetry requires a Metrics instance")
        self._metrics = metrics
        if self.input_cost_per_token is not None and self.input_cost_per_token < 0:
            raise ValueError("input_cost_per_token must be >= 0")
        if self.output_cost_per_token is not None and self.output_cost_per_token < 0:
            raise ValueError("output_cost_per_token must be >= 0")

    @property
    def metrics(self) -> Metrics:
        return self._metrics

    # ---------- Lifecycle ----------
    def set_metrics(self, metrics: Metrics) -> None:
        self._metrics = metrics

    def on_request(self, log_ctx: dict | None) -> None:
        self._req_start = time.time()
        self._req_ctx = log_ctx or {}

    def on_response(
        self,
        resp: ModelResponse | ResponsesAPIResponse,
        raw_resp: ModelResponse | ResponsesAPIResponse | None = None,
    ) -> Metrics:
        """
        Backward-compatible shim: dispatch to typed handlers.
        """
        if isinstance(resp, ModelResponse):
            raw = raw_resp if isinstance(raw_resp, ModelResponse) else None
            return self.on_completion_response(resp, raw_resp=raw)
        if isinstance(resp, ResponsesAPIResponse):
            raw = raw_resp if isinstance(raw_resp, ResponsesAPIResponse) else None
            return self.on_responses_response(resp, raw_resp=raw)
        return self._metrics.deep_copy()

    def on_completion_response(
        self, resp: ModelResponse, raw_resp: ModelResponse | None = None
    ) -> Metrics:
        # latency
        self._last_latency = time.time() - (self._req_start or time.time())
        response_id = str(resp.id)
        self._metrics.add_response_latency(self._last_latency, response_id)

        # cost
        cost = self._compute_cost(resp)
        if cost:
            self._metrics.add_cost(cost)

        # tokens
        usage = resp.usage
        if usage:
            pt = int((usage.prompt_tokens or 0))
            ct = int((usage.completion_tokens or 0))
            if pt > 0 or ct > 0:
                self._record_usage_completion(
                    usage, response_id, self._req_ctx.get("context_window", 0)
                )

        if self.log_enabled:
            self.log_llm_call(resp, cost, raw_resp=raw_resp)
        return self._metrics.deep_copy()

    def on_responses_response(
        self, resp: ResponsesAPIResponse, raw_resp: ResponsesAPIResponse | None = None
    ) -> Metrics:
        # latency
        self._last_latency = time.time() - (self._req_start or time.time())
        response_id = str(resp.id)
        self._metrics.add_response_latency(self._last_latency, response_id)

        # cost
        cost = self._compute_cost(resp)
        if cost:
            self._metrics.add_cost(cost)

        # tokens
        usage = resp.usage
        if usage:
            pt = int((usage.input_tokens or 0))
            ct = int((usage.output_tokens or 0))
            if pt > 0 or ct > 0:
                self._record_usage_responses(
                    usage, response_id, self._req_ctx.get("context_window", 0)
                )

        if self.log_enabled:
            self.log_llm_call(resp, cost, raw_resp=raw_resp)
        return self._metrics.deep_copy()

    def on_error(self, _err: Exception) -> None:
        # Stub for error tracking / counters
        return

    # ---------- Helpers ----------
    def _record_usage_completion(
        self, usage: Usage, response_id: str, context_window: int
    ) -> None:
        prompt_tokens = int(usage.prompt_tokens or 0)
        completion_tokens = int(usage.completion_tokens or 0)
        cache_read = 0
        if getattr(usage, "prompt_tokens_details", None) is not None:
            cache_read = int(getattr(usage.prompt_tokens_details, "cached_tokens", 0) or 0)
        reasoning_tokens = 0
        if getattr(usage, "completion_tokens_details", None) is not None:
            reasoning_tokens = int(
                getattr(usage.completion_tokens_details, "reasoning_tokens", 0) or 0
            )
        cache_write = int(getattr(usage, "_cache_creation_input_tokens", 0) or 0)
        self._metrics.add_token_usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            reasoning_tokens=reasoning_tokens,
            context_window=context_window,
            response_id=response_id,
        )

    def _record_usage_responses(
        self, usage: ResponseAPIUsage, response_id: str, context_window: int
    ) -> None:
        prompt_tokens = int(usage.input_tokens or 0)
        completion_tokens = int(usage.output_tokens or 0)
        cache_read = 0
        if getattr(usage, "input_tokens_details", None) is not None:
            cache_read = int(getattr(usage.input_tokens_details, "cached_tokens", 0) or 0)
        reasoning_tokens = 0
        if getattr(usage, "output_tokens_details", None) is not None:
            reasoning_tokens = int(
                getattr(usage.output_tokens_details, "reasoning_tokens", 0) or 0
            )
        cache_write = 0
        self._metrics.add_token_usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            reasoning_tokens=reasoning_tokens,
            context_window=context_window,
            response_id=response_id,
        )

    def _compute_cost(self, resp: ModelResponse | ResponsesAPIResponse) -> float | None:
        """Try provider header → litellm direct. Return None on failure."""
        extra_kwargs: dict[str, Any] = {}
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

        try:
            hidden = getattr(resp, "_hidden_params", {}) or {}
            cost = hidden.get("additional_headers", {}).get(
                "llm_provider-x-litellm-response-cost"
            )
            if cost is not None:
                return float(cost)
        except Exception as e:
            logger.debug(f"Failed to get cost from LiteLLM headers: {e}")

        # move on to litellm cost calculator
        # Handle model name properly - if it doesn't contain "/", use as-is
        model_parts = self.model_name.split("/")
        if len(model_parts) > 1:
            extra_kwargs["model"] = "/".join(model_parts[1:])
        else:
            extra_kwargs["model"] = self.model_name
        try:
            return float(
                litellm_completion_cost(completion_response=resp, **extra_kwargs)
            )
        except Exception as e:
            warnings.warn(f"Cost calculation failed: {e}")
            return None

    def log_llm_call(
        self,
        resp: ModelResponse | ResponsesAPIResponse,
        cost: float | None,
        raw_resp: ModelResponse | ResponsesAPIResponse | None = None,
    ) -> None:
        if not self.log_dir:
            return
        try:
            # Only log if directory exists and is writable.
            # Do not create directories implicitly.
            if not os.path.isdir(self.log_dir):
                raise FileNotFoundError(f"log_dir does not exist: {self.log_dir}")
            if not os.access(self.log_dir, os.W_OK):
                raise PermissionError(f"log_dir is not writable: {self.log_dir}")

            fname = os.path.join(
                self.log_dir,
                (
                    f"{self.model_name.replace('/', '__')}-"
                    f"{time.time():.3f}-"
                    f"{uuid.uuid4().hex[:4]}.json"
                ),
            )
            data = self._req_ctx.copy()
            data["response"] = (
                resp  # ModelResponse | ResponsesAPIResponse;
                # serialized via _safe_json
            )
            data["cost"] = float(cost or 0.0)
            data["timestamp"] = time.time()
            data["latency_sec"] = self._last_latency

            # Usage summary (prompt, completion, reasoning tokens) for quick inspection
            try:
                usage = resp.usage
                if usage:
                    prompt_tokens = int(
                        getattr(usage, "prompt_tokens", None)
                        or getattr(usage, "input_tokens", 0)
                        or 0
                    )
                    completion_tokens = int(
                        getattr(usage, "completion_tokens", None)
                        or getattr(usage, "output_tokens", 0)
                        or 0
                    )
                    details = getattr(
                        usage, "completion_tokens_details", None
                    ) or getattr(usage, "output_tokens_details", None)
                    reasoning_tokens = (
                        int(getattr(details, "reasoning_tokens", 0) or 0)
                        if details
                        else 0
                    )
                    p_details = getattr(
                        usage, "prompt_tokens_details", None
                    ) or getattr(usage, "input_tokens_details", None)
                    cache_read_tokens = (
                        int(getattr(p_details, "cached_tokens", 0) or 0)
                        if p_details
                        else 0
                    )

                    data["usage_summary"] = {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "reasoning_tokens": reasoning_tokens,
                        "cache_read_tokens": cache_read_tokens,
                    }
            except Exception:
                # Best-effort only; don't fail logging
                pass

            # Raw response *before* nonfncall -> call conversion
            if raw_resp:
                data["raw_response"] = (
                    raw_resp  # ModelResponse | ResponsesAPIResponse;
                    # serialized via _safe_json
                )
            # Pop duplicated tools to avoid logging twice
            if (
                "tools" in data
                and isinstance(data.get("kwargs"), dict)
                and "tools" in data["kwargs"]
            ):
                data["kwargs"].pop("tools")
            with open(fname, "w") as f:
                f.write(json.dumps(data, default=_safe_json))
        except Exception as e:
            warnings.warn(f"Telemetry logging failed: {e}")


def _safe_json(obj: Any) -> Any:
    # Centralized serializer for telemetry logs.
    # Today, responses are Pydantic ModelResponse or ResponsesAPIResponse; rely on it.
    if isinstance(obj, ModelResponse) or isinstance(obj, ResponsesAPIResponse):
        return obj.model_dump()

    # Fallbacks for non-Pydantic objects used elsewhere in the log payload
    try:
        return obj.__dict__
    except Exception:
        return str(obj)
