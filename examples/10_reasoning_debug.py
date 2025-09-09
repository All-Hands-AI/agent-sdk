import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    Event,
    ImageContent,
    Message,
    TextContent,
    Tool,
    get_logger,
)
from openhands.sdk.conversation import ConversationVisualizer
from openhands.sdk.llm.utils.model_features import get_features
from openhands.sdk.tool import ActionBase, ObservationBase, ToolExecutor


logger = get_logger(__name__)


# Calculator tool implementation
class CalculateAction(ActionBase):
    """Action to calculate a mathematical expression."""

    expression: str = Field(
        description="Mathematical expression to evaluate (e.g., '2+2', '78*964')"
    )


class CalculateObservation(ObservationBase):
    """Observation containing the calculation result."""

    result: str = Field(description="The result of the calculation")
    error: str | None = Field(
        default=None, description="Error message if calculation failed"
    )

    @property
    def agent_observation(self) -> list[TextContent | ImageContent]:
        """Get the observation to show to the agent."""
        if self.error:
            return [TextContent(text=f"Error: {self.error}")]
        return [TextContent(text=f"Result: {self.result}")]


class CalculatorExecutor(ToolExecutor):
    """Executor for the calculator tool."""

    def __call__(self, action: CalculateAction) -> CalculateObservation:
        """Execute a calculation safely."""
        try:
            # Simple safe evaluation for basic math
            import ast
            import operator

            # Supported operations
            ops = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.Pow: operator.pow,
                ast.USub: operator.neg,
            }

            def eval_expr(node):
                if isinstance(node, ast.Constant):
                    return node.value
                elif isinstance(node, ast.BinOp):
                    return ops[type(node.op)](
                        eval_expr(node.left), eval_expr(node.right)
                    )
                elif isinstance(node, ast.UnaryOp):
                    return ops[type(node.op)](eval_expr(node.operand))
                else:
                    raise TypeError(f"Unsupported operation: {type(node)}")

            result = eval_expr(ast.parse(action.expression, mode="eval").body)
            return CalculateObservation(result=str(result))
        except Exception as e:
            return CalculateObservation(
                result="", error=f"Error calculating {action.expression}: {e}"
            )


def _create_calculator_tool() -> Tool:
    """Create a calculator tool for testing tools + reasoning."""
    return Tool(
        name="calculate",
        description=(
            "Calculate a mathematical expression safely. "
            "Supports basic arithmetic operations (+, -, *, /, **) and parentheses."
        ),
        input_schema=CalculateAction,
        output_schema=CalculateObservation,
        executor=CalculatorExecutor(),
    )


def _default_model_entries(proxy_base: str) -> list[dict[str, str | None]]:
    return [
        {
            "label": "proxy/gpt-5-mini-2025-08-07",
            "model": "litellm_proxy/openai/gpt-5-mini-2025-08-07",
            "base_url": proxy_base,
            "api_key_env": "LITELLM_API_KEY",
        },
        # {
        #     "label": "deepseek-direct/reasoner",
        #     "model": "deepseek/deepseek-reasoner",
        #     "base_url": deepseek_base,
        #     "api_key_env": "DEEPSEEK_API_KEY",
        # },
        # {
        #     "label": "proxy/deepseek-reasoner",
        #     "model": "litellm_proxy/deepseek/deepseek-reasoner",
        #     "base_url": proxy_base,
        #     "api_key_env": "LITELLM_API_KEY",
        # },
        # {
        #     "label": "proxy/gemini-2.5-pro",
        #     "model": "litellm_proxy/gemini/gemini-2.5-pro",
        #     "base_url": proxy_base,
        #     "api_key_env": "LITELLM_API_KEY",
        # },
        # {
        #     "label": "gemini-direct/gemini-2.5-pro",
        #     "model": "gemini/gemini-2.5-pro",
        #     "base_url": None,
        #     "api_key_env": "GEMINI_API_KEY",
        # },
    ]


def _infer_entry(m: str, proxy_base: str) -> dict[str, str | None]:
    if m.startswith("deepseek/"):
        return {
            "label": f"deepseek-direct/{m.split('/')[-1]}",
            "model": m,
            "base_url": "https://api.deepseek.com",
            "api_key_env": "DEEPSEEK_API_KEY",
        }
    if m.startswith("gemini/"):
        return {
            "label": f"gemini-direct/{m.split('/')[-1]}",
            "model": m,
            "base_url": None,
            "api_key_env": "GEMINI_API_KEY",
        }
    return {
        "label": f"proxy/{m}",
        "model": m if m.startswith("litellm_proxy/") else f"litellm_proxy/{m}",
        "base_url": proxy_base,
        "api_key_env": "LITELLM_API_KEY",
    }


def _resolve_models_from_env(proxy_base: str) -> list[dict[str, str | None]]:
    models_env = os.getenv("REASONING_MODELS")
    model_env = os.getenv("REASONING_MODEL")
    if models_env:
        model_ids = [s.strip() for s in models_env.split(",") if s.strip()]
        return [_infer_entry(m, proxy_base) for m in model_ids]
    if model_env:
        return [_infer_entry(model_env.strip(), proxy_base)]
    return _default_model_entries(proxy_base)


def test_reasoning_content_oh() -> None:
    """Probe reasoning using OpenHands LLM and Conversation.

    Logs raw completions, surfaces reasoning_content from events and llm_message,
    and prints a summary including reasoning_tokens from metrics.
    """

    task = os.getenv(
        "REASONING_TASK",
        (
            "Solve this carefully and show your internal reasoning as available: "
            "78*964 + 17. You have access to a calculator tool if needed."
        ),
    )

    proxy_base = os.getenv("LITELLM_BASE_URL", "https://llm-proxy.eval.all-hands.dev")

    model_entries = _resolve_models_from_env(proxy_base)

    print("\n=== OH reasoning probe: starting ===\n")
    results: list[dict[str, Any]] = []

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

        print(f"\n--- Testing {label} ({model}) ---\n")

        llm = LLM(
            model=model,
            base_url=base_url,  # type: ignore[arg-type]
            api_key=SecretStr(api_key_val),
            log_completions=True,
            reasoning_effort="high",
        )

        # Add a simple calculator tool to test tools + reasoning
        tools: list[Tool] = [_create_calculator_tool()]
        agent = Agent(llm=llm, tools=tools)
        visualizer = ConversationVisualizer()

        saw_reasoning = False
        last_reasoning_tokens = 0

        def on_event(event: Event) -> None:
            nonlocal saw_reasoning
            visualizer.on_event(event)

            rc = getattr(event, "reasoning_content", None)
            if rc:
                saw_reasoning = True
                print("\n==== reasoning_content (from event) ====\n")
                print(rc)
                print("=======================================\n")

            if hasattr(event, "llm_message"):
                llm_msg = getattr(event, "llm_message")
                msg_rc = getattr(llm_msg, "reasoning_content", None)
                if msg_rc:
                    saw_reasoning = True
                    print("\n==== reasoning_content (from llm_message) ====\n")
                    print(msg_rc)
                    print("============================================\n")

        # Test responses API (note: has limitations with GPT-5 models)
        print("\n" + "=" * 50)
        print("RESPONSES API TEST")
        print("=" * 50)
        if llm.is_responses_api_supported():
            print("✅ Model supports Responses API")
            try:
                # Test responses API without tools (tools cause litellm bug)
                resp = llm.responses(input="What is 2+2?")
                print("✅ Responses API call successful")
                if hasattr(resp, "usage"):
                    usage = getattr(resp, "usage", None)
                    if usage:
                        print(f"📊 Usage: {usage}")

                # Note: Responses API currently has limitations with GPT-5 models
                # - Empty content returned
                # - No reasoning_content field
                # - Tools cause "empty function name" error
                print("⚠️  Note: Responses API has known limitations with GPT-5 models")
                print("   - Content may be empty")
                print("   - reasoning_content field not available")
                print("   - Tools integration has issues")
            except Exception as e:
                print(f"❌ Responses API failed: {e}")
        else:
            print("❌ Model does not support Responses API")
        print("=" * 50 + "\n")

        # Test regular conversation flow (this works perfectly with GPT-5)
        print("=" * 50)
        print("CONVERSATION FLOW TEST")
        print("=" * 50)
        conversation = Conversation(agent=agent, callbacks=[on_event])
        conversation.send_message(
            message=Message(role="user", content=[TextContent(text=task)])
        )
        conversation.run()
        print("✅ Conversation completed successfully")
        m = agent.llm.metrics
        if m and m.token_usages:
            last_reasoning_tokens = m.token_usages[-1].reasoning_tokens
        results.append(
            {
                "model": model,
                "label": label,
                "result": "YES" if saw_reasoning else "NO",
                "reasoning_tokens": last_reasoning_tokens,
            }
        )

    # Persist results
    out_dir = Path(os.getenv("REASONING_LOG_DIR", "logs"))
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    with open(out_dir / f"reasoning_probe_oh_{ts}.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== OH reasoning probe: summary ===")
    for r in results:
        summary = (
            f"- {r['label']} ({r['model']}): {r['result']} | "
            f"reasoning_tokens={r.get('reasoning_tokens', 0)}"
        )
        print(summary)
    print("=== End ===\n")


def test_reasoning_litellm() -> None:
    """Probe reasoning by calling litellm.completion directly.

    Sends the same prompt to each model, passes reasoning flags if supported,
    and prints whether message.reasoning_content is present plus tokens.
    """

    import litellm  # local import for example

    task = os.getenv(
        "REASONING_TASK",
        (
            "Solve this carefully and show your internal reasoning as available: "
            "78*964 + 17. Respond with the final integer answer."
        ),
    )

    proxy_base = os.getenv("LITELLM_BASE_URL", "https://llm-proxy.eval.all-hands.dev")

    model_entries = _resolve_models_from_env(proxy_base)

    print("\n=== LiteLLM reasoning probe: starting ===\n")
    results: list[dict[str, Any]] = []

    for entry in model_entries:
        label = str(entry["label"])  # type: ignore[index]
        model = str(entry["model"])  # type: ignore[index]
        base_url = entry["base_url"]  # type: ignore[index]
        api_key_env = str(entry["api_key_env"])  # type: ignore[index]

        if (
            "o3" in model
            and not os.getenv("REASONING_MODELS")
            and not os.getenv("REASONING_MODEL")
        ):
            continue

        api_key_val = os.getenv(api_key_env)
        if not api_key_val:
            print(f"[skip] {label}: missing API key env {api_key_env}")
            results.append({"model": model, "label": label, "result": "SKIPPED"})
            continue

        print(f"\n--- Testing {label} ({model}) ---\n")
        kwargs: dict[str, Any] = {}

        if get_features(model).supports_reasoning_effort:
            kwargs["reasoning_effort"] = "high"

        # Skip Gemini 'thinking' param to avoid proxy incompatibilities
        # and rely on provider defaults / LiteLLM normalization.

        messages = [
            {"role": "user", "content": task},
        ]

        try:
            resp = litellm.completion(
                model=model,
                api_key=api_key_val,
                base_url=base_url,
                messages=messages,
                stream=False,
                **kwargs,
            )
            saw_reasoning = False
            try:
                choices = getattr(resp, "choices", None)
                if choices:
                    first = choices[0]  # type: ignore[index]
                    message = getattr(first, "message", None)
                    msg_rc = getattr(message, "reasoning_content", None)
                    if msg_rc:
                        saw_reasoning = True
                        print("\n==== reasoning_content (from litellm message) ====\n")
                        print(msg_rc)
                        print("===============================================\n")
            except Exception:
                pass

            reasoning_tokens = 0
            try:
                usage = getattr(resp, "usage", None)
                if usage:
                    details = getattr(usage, "completion_tokens_details", None)
                    if details and getattr(details, "reasoning_tokens", None):
                        reasoning_tokens = int(details.reasoning_tokens)
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
                    "reasoning_tokens": 0,
                }
            )

    print("\n=== LiteLLM reasoning probe: summary ===")
    for r in results:
        summary = (
            f"- {r['label']} ({r['model']}): {r['result']} | "
            f"reasoning_tokens={r.get('reasoning_tokens', 0)}"
        )
        print(summary)
    print("=== End ===\n")
    # Persist results
    out_dir = Path(os.getenv("REASONING_LOG_DIR", "logs"))
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    with open(out_dir / f"reasoning_probe_litellm_{ts}.json", "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    test_reasoning_content_oh()
    # test_reasoning_litellm() # uncomment to run both probes
