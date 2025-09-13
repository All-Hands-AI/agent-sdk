import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    get_logger,
)


logger = get_logger(__name__)


def _default_model_entries(proxy_base: str) -> list[dict[str, str | None]]:
    # Only test the required model via LiteLLM proxy
    return [
        {
            "label": "proxy/gpt-5-mini-2025-08-07",
            "model": "litellm_proxy/openai/gpt-5-mini-2025-08-07",
            "base_url": proxy_base,
            "api_key_env": "LITELLM_API_KEY",
        }
    ]


def _infer_entry(m: str, proxy_base: str) -> dict[str, str | None]:
    # Force everything through the proxy, only for the GPT-5-mini model.
    return {
        "label": f"proxy/{m}",
        "model": m if m.startswith("litellm_proxy/") else f"litellm_proxy/{m}",
        "base_url": proxy_base,
        "api_key_env": "LITELLM_API_KEY",
    }


def _resolve_models_from_env(proxy_base: str) -> list[dict[str, str | None]]:
    # Always return only the GPT-5-mini model via proxy
    return _default_model_entries(proxy_base)


def test_reasoning_oh_responses() -> None:
    """Probe reasoning using OpenHands LLM.responses() (OpenAI Responses API).

    Calls the Responses API path explicitly, verifies reasoning_content is
    surfaced via our responses_converter, records reasoning_tokens if present,
    and persists JSON results.
    """

    task = os.getenv(
        "REASONING_TASK",
        (
            "Solve this carefully and show your internal reasoning as available: "
            "78*964 + 17."
        ),
    )

    proxy_base = os.getenv("LITELLM_BASE_URL", "https://llm-proxy.eval.all-hands.dev")

    model_entries = _resolve_models_from_env(proxy_base)

    print("\n=== OH Responses API probe: starting ===\n")
    results: list[dict[str, Any]] = []

    # Ensure audit log directory exists and wire Telemetry there
    out_dir = Path(os.getenv("REASONING_LOG_DIR", "logs/reasoning"))
    out_dir.mkdir(parents=True, exist_ok=True)

    for entry in model_entries:
        label = str(entry["label"])  # type: ignore[index]
        model = str(entry["model"])  # type: ignore[index]
        base_url = entry["base_url"]  # type: ignore[index]
        api_key_env = str(entry["api_key_env"])  # type: ignore[index]

        api_key_val = os.getenv(api_key_env)
        if not api_key_val:
            print(f"[skip] {label}: missing API key env {api_key_env}")
            results.append({"model": model, "label": label, "result": "SKIPPED"})
            continue

        print(f"\n--- Testing {label} ({model}) [Responses API] ---\n")

        llm = LLM(
            model=model,
            base_url=base_url,  # type: ignore[arg-type]
            api_key=SecretStr(api_key_val),
            log_completions=True,
            log_completions_folder=str(out_dir),
            reasoning_effort="high",
        )

        saw_reasoning = False
        reasoning_tokens = 0
        try:
            # Use the explicit Responses API path
            resp = llm.responses(input=task)

            # Extract reasoning_content from converted response
            try:
                choices = getattr(resp, "choices", None)
                if choices:
                    first = choices[0]  # type: ignore[index]
                    message = getattr(first, "message", None)
                    msg_rc = getattr(message, "reasoning_content", None)
                    if msg_rc:
                        saw_reasoning = True
                        print("\n==== reasoning_content (OH Responses) ====\n")
                        print(msg_rc)
                        print("==========================================\n")
            except Exception:
                pass

            try:
                m = llm.metrics
                if m and m.token_usages:
                    reasoning_tokens = int(m.token_usages[-1].reasoning_tokens)
            except Exception:
                pass

            results.append(
                {
                    "model": model,
                    "label": label,
                    "result": "YES" if saw_reasoning else "NO",
                    "reasoning_tokens": reasoning_tokens,
                }
            )
        except Exception as e:  # noqa: BLE001
            print(f"[error] {label}: {e}")
            results.append(
                {
                    "model": model,
                    "label": label,
                    "result": f"ERROR: {type(e).__name__}: {e}",
                    "reasoning_tokens": reasoning_tokens,
                }
            )

    # Persist results
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    with open(out_dir / f"reasoning_probe_oh_responses_{ts}.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== OH Responses API probe: summary ===")
    for r in results:
        summary = (
            f"- {r['label']} ({r['model']}): {r['result']} | "
            f"reasoning_tokens={r.get('reasoning_tokens', 0)}"
        )
        print(summary)
    print("=== End ===\n")


def test_reasoning_oh_completion_delegation() -> None:
    """Probe reasoning by calling llm.completion() on a Responses-capable model.

    This verifies that completion() transparently delegates to the Responses API
    and that reasoning_content and reasoning_tokens are surfaced.
    """

    task = os.getenv(
        "REASONING_TASK",
        (
            "Solve this carefully and show your internal reasoning as available: "
            "78*964 + 17."
        ),
    )

    proxy_base = os.getenv("LITELLM_BASE_URL", "https://llm-proxy.eval.all-hands.dev")

    model_entries = _resolve_models_from_env(proxy_base)

    print("\n=== OH completion() delegation probe: starting ===\n")
    results: list[dict[str, Any]] = []

    # Ensure audit log directory exists and wire Telemetry there
    out_dir = Path(os.getenv("REASONING_LOG_DIR", "logs/reasoning"))
    out_dir.mkdir(parents=True, exist_ok=True)

    for entry in model_entries:
        label = str(entry["label"])  # type: ignore[index]
        model = str(entry["model"])  # type: ignore[index]
        base_url = entry["base_url"]  # type: ignore[index]
        api_key_env = str(entry["api_key_env"])  # type: ignore[index]

        api_key_val = os.getenv(api_key_env)
        if not api_key_val:
            print(f"[skip] {label}: missing API key env {api_key_env}")
            results.append({"model": model, "label": label, "result": "SKIPPED"})
            continue

        print(f"\n--- Testing {label} ({model}) [completion()->Responses] ---\n")

        llm = LLM(
            model=model,
            base_url=base_url,  # type: ignore[arg-type]
            api_key=SecretStr(api_key_val),
            log_completions=True,
            log_completions_folder=str(out_dir),
            reasoning_effort="high",
        )

        saw_reasoning = False
        reasoning_tokens = 0

        messages = [
            {"role": "user", "content": task},
        ]

        try:
            resp = llm.completion(messages=messages)

            # Extract reasoning_content from converted response
            try:
                choices = getattr(resp, "choices", None)
                if choices:
                    first = choices[0]  # type: ignore[index]
                    message = getattr(first, "message", None)
                    msg_rc = getattr(message, "reasoning_content", None)
                    if msg_rc:
                        saw_reasoning = True
                        print("\n==== reasoning_content (OH completion) ====\n")
                        print(msg_rc)
                        print("====================================================\n")
            except Exception:
                pass

            try:
                m = llm.metrics
                if m and m.token_usages:
                    reasoning_tokens = int(m.token_usages[-1].reasoning_tokens)
            except Exception:
                pass

            results.append(
                {
                    "model": model,
                    "label": label,
                    "result": "YES" if saw_reasoning else "NO",
                    "reasoning_tokens": reasoning_tokens,
                }
            )
        except Exception as e:  # noqa: BLE001
            print(f"[error] {label}: {e}")
            results.append(
                {
                    "model": model,
                    "label": label,
                    "result": f"ERROR: {type(e).__name__}: {e}",
                    "reasoning_tokens": reasoning_tokens,
                }
            )

    # Persist results
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    with open(out_dir / f"reasoning_probe_oh_completion_{ts}.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== OH completion() delegation probe: summary ===")
    for r in results:
        summary = (
            f"- {r['label']} ({r['model']}): {r['result']} | "
            f"reasoning_tokens={r.get('reasoning_tokens', 0)}"
        )
        print(summary)
    print("=== End ===\n")


if __name__ == "__main__":
    # test_reasoning_content_oh() # optional first probe
    test_reasoning_oh_completion_delegation()
    test_reasoning_oh_responses()
    # test_reasoning_litellm() # optional third probe
