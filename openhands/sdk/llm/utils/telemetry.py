import json
import os
import time
import warnings
from typing import Any, Optional

from litellm.cost_calculator import completion_cost as litellm_completion_cost
from litellm.types.utils import CostPerToken, ModelResponse, Usage
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from openhands.sdk.llm.utils.metrics import Metrics
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


class Telemetry(BaseModel):
    """
    Handles latency, token/cost accounting, and optional logging.
    All runtime state (like start times) lives in private attrs.
    """

    # --- Config fields ---
    model_name: str = Field(default="unknown", description="Name of the LLM model")
    log_enabled: bool = Field(default=False, description="Whether to log completions")
    log_dir: Optional[str] = Field(
        default=None, description="Directory to write logs if enabled"
    )
    input_cost_per_token: float | None = Field(
        default=None, description="Custom Input cost per token (USD)"
    )
    output_cost_per_token: float | None = Field(
        default=None, description="Custom Output cost per token (USD)"
    )

    metrics: Metrics = Field(..., description="Metrics collector instance")

    # --- Runtime fields (not serialized) ---
    _req_start: float = PrivateAttr(default=0.0)
    _req_ctx: dict[str, Any] = PrivateAttr(default_factory=dict)
    _last_latency: float = PrivateAttr(default=0.0)

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    # ---------- Lifecycle ----------
    def on_request(self, log_ctx: dict | None) -> None:
        self._req_start = time.time()
        self._req_ctx = log_ctx or {}

    def on_response(
        self, resp: ModelResponse, raw_resp: ModelResponse | None = None
    ) -> Metrics:
        """
        Side-effects:
          - records latency, tokens, cost into Metrics
          - optionally writes a JSON log file
        """
        # 1) latency
        self._last_latency = time.time() - (self._req_start or time.time())
        response_id = resp.id
        self.metrics.add_response_latency(self._last_latency, response_id)

        # 2) cost
        cost = self._compute_cost(resp)
        if cost:
            self.metrics.add_cost(cost)

        # 3) tokens - handle both dict and ModelResponse objects
        if isinstance(resp, dict):
            usage = resp.get("usage")
        else:
            usage = getattr(resp, "usage", None)

        if usage and self._has_meaningful_usage(usage):
            self._record_usage(
                usage, response_id, self._req_ctx.get("context_window", 0)
            )

        # 4) optional logging
        if self.log_enabled:
            self._log_completion(resp, cost, raw_resp=raw_resp)

        return self.metrics.deep_copy()

    def on_error(self, err: Exception) -> None:
        # Stub for error tracking / counters
        return

    # ---------- Helpers ----------
    def _has_meaningful_usage(self, usage) -> bool:
        """Check if usage has meaningful (non-zero) token counts."""
        if not usage:
            return False

        # Handle MagicMock objects safely
        try:
            if isinstance(usage, dict):
                prompt_tokens = usage.get("prompt_tokens", 0) or 0
                completion_tokens = usage.get("completion_tokens", 0) or 0
            else:
                prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
                completion_tokens = getattr(usage, "completion_tokens", 0) or 0

            # Convert to int safely (handles MagicMock objects)
            prompt_tokens = int(prompt_tokens) if str(prompt_tokens).isdigit() else 0
            completion_tokens = (
                int(completion_tokens) if str(completion_tokens).isdigit() else 0
            )

            return prompt_tokens > 0 or completion_tokens > 0
        except (ValueError, TypeError, AttributeError):
            return False

    def _record_usage(
        self, usage: Usage, response_id: str, context_window: int
    ) -> None:
        # Handle both dict and Usage objects
        if isinstance(usage, dict):
            usage = Usage.model_validate(usage)

        prompt_tokens = usage.prompt_tokens or 0
        completion_tokens = usage.completion_tokens or 0
        cache_write = usage._cache_creation_input_tokens or 0

        cache_read = 0
        prompt_token_details = usage.prompt_tokens_details or None
        if prompt_token_details and prompt_token_details.cached_tokens:
            cache_read = prompt_token_details.cached_tokens

        reasoning_tokens = 0
        completion_tokens_details = usage.completion_tokens_details or None
        if completion_tokens_details and completion_tokens_details.reasoning_tokens:
            reasoning_tokens = completion_tokens_details.reasoning_tokens

        self.metrics.add_token_usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            reasoning_tokens=reasoning_tokens,
            context_window=context_window,
            response_id=response_id,
        )

    def _compute_cost(self, resp: ModelResponse) -> Optional[float]:
        """Try provider header → litellm direct. Return None on failure."""
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

    def _log_completion(
        self,
        resp: ModelResponse,
        cost: Optional[float],
        raw_resp: ModelResponse | None = None,
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
                f"{self.model_name.replace('/', '__')}-{time.time():.3f}.json",
            )
            data = self._req_ctx.copy()
            data["response"] = resp.model_dump()
            data["cost"] = float(cost or 0.0)
            data["timestamp"] = time.time()
            data["latency_sec"] = self._last_latency

            # Usage summary (prompt, completion, reasoning tokens) for quick inspection
            try:
                usage = getattr(resp, "usage", None)
                if usage:
                    if isinstance(usage, dict):
                        usage = Usage.model_validate(usage)
                    prompt_tokens = int(usage.prompt_tokens or 0)
                    completion_tokens = int(usage.completion_tokens or 0)
                    reasoning_tokens = 0
                    details = usage.completion_tokens_details or None
                    if details and details.reasoning_tokens:
                        reasoning_tokens = int(details.reasoning_tokens)
                    data["usage_summary"] = {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "reasoning_tokens": reasoning_tokens,
                    }
                    if usage.prompt_tokens_details:
                        data["usage_summary"]["cache_read_tokens"] = int(
                            usage.prompt_tokens_details.cached_tokens or 0
                        )
            except Exception:
                # Best-effort only; don't fail logging
                pass

            # Raw response *before* nonfncall -> call conversion
            if raw_resp:
                data["raw_response"] = raw_resp
            # pop duplicated tools
            if "tool" in data and "tool" in data.get("kwargs", {}):
                data["kwargs"].pop("tool")
            with open(fname, "w") as f:
                f.write(json.dumps(data, default=_safe_json))
        except Exception as e:
            warnings.warn(f"Telemetry logging failed: {e}")


def _safe_json(obj: Any) -> Any:
    try:
        return obj.__dict__
    except Exception:
        return str(obj)
