import glob
import json
import os
import time
from typing import Any

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Conversation,
    EventBase,
    LLMConvertibleEvent,
    get_logger,
)
from openhands.sdk.preset.default import get_default_agent


logger = get_logger(__name__)


def analyze_logs(log_dir: str) -> dict[str, Any]:
    files = sorted(
        glob.glob(os.path.join(log_dir, "*.json")), key=lambda p: os.path.getmtime(p)
    )
    if not files:
        print(f"No logs found in {log_dir}")
        return {"files": 0}

    total = len(files)
    with_tool_calls = 0
    with_tool_role = 0
    first_tool_call: dict[str, Any] | None = None

    for path in files:
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception as e:
            print(f"Failed to read {path}: {e}")
            continue

        # Request messages (dict-based for logging)
        msgs = data.get("messages", []) or []
        if any(isinstance(m, dict) and m.get("role") == "tool" for m in msgs):
            with_tool_role += 1

        # Response (ModelResponse.dump)
        resp = data.get("response")
        if resp and isinstance(resp, dict):
            choices = resp.get("choices") or []
            for ch in choices:
                msg = ch.get("message") or {}
                tcs = msg.get("tool_calls") or []
                if tcs:
                    with_tool_calls += 1
                    if first_tool_call is None:
                        first_tool_call = tcs[0]
                    break

    summary = {
        "files": total,
        "request_with_tool_role": with_tool_role,
        "responses_with_tool_calls": with_tool_calls,
        "first_tool_call": first_tool_call,
    }

    print("=" * 100)
    print("E2E log analysis summary:")
    print(json.dumps(summary, indent=2))
    print("=" * 100)

    if first_tool_call:
        fn = first_tool_call.get("function", {})
        print(
            f"First tool call -> id={first_tool_call.get('id')} "
            f"type={first_tool_call.get('type')} "
            f"name={fn.get('name')}\narguments={fn.get('arguments')}"
        )

    return summary


if __name__ == "__main__":
    # Configure LLM
    api_key = os.getenv("LITELLM_API_KEY")
    assert api_key, "LITELLM_API_KEY environment variable is not set"

    log_dir = os.path.join(os.getcwd(), "logs", "typed")
    os.makedirs(log_dir, exist_ok=True)

    llm = LLM(
        service_id="agent",
        model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
        base_url="https://llm-proxy.eval.all-hands.dev",
        api_key=SecretStr(api_key),
        log_completions=True,
        log_completions_folder=log_dir,
    )

    # Agent with default preset (CLI mode: no browser tools)
    agent = get_default_agent(llm=llm, working_dir=os.getcwd(), cli_mode=True)

    # Collect LLM messages, if desired
    llm_messages = []

    def conversation_callback(event: EventBase):
        if isinstance(event, LLMConvertibleEvent):
            llm_messages.append(event.to_llm_message())

    conversation = Conversation(agent=agent, callbacks=[conversation_callback])

    # Prompt encouraging tool usage to read the README first
    msg = (
        "Read the repository's README.md from the project root using the available "
        "tools, then provide a concise summary in 3 bullet points."
    )
    conversation.send_message(msg)

    # Run the conversation end-to-end
    print("Running conversation...")
    start = time.time()
    conversation.run()
    print(f"Conversation finished in {time.time() - start:.2f}s")

    # Analyze logs to verify tool calls & typed flow
    analyze_logs(log_dir)
