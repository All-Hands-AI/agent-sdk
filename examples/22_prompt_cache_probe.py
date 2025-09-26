"""OpenHands Agent SDK — Prompt Cache Probe (Anthropic)

This example runs a short task using an Anthropic model via LiteLLM proxy,
logs completion metadata, and prints whether prompt caching (read/write tokens)
appears in the usage.

Requirements:
- LITELLM_API_KEY set in the environment
- Network access to the LiteLLM proxy

It will:
1) Create an LLM with logging enabled (JSON logs written to a temp dir)
2) Create a default agent with bash/file editor tools
3) Ask the agent to read README.mdx and summarize it
4) Print a summary of cache read/write tokens from the telemetry logs
"""

import glob
import json
import os
import signal
import time
from pathlib import Path

import litellm
from pydantic import SecretStr

from openhands.sdk import Conversation
from openhands.sdk.llm.llm import LLM
from openhands.sdk.preset.default import get_default_agent
from openhands.sdk.security.confirmation_policy import NeverConfirm


# Make ^C a clean exit instead of a stack trace
signal.signal(signal.SIGINT, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))


def main() -> None:
    api_key = os.getenv("LITELLM_API_KEY")
    assert api_key, "LITELLM_API_KEY environment variable is not set."

    # Create a writable logs directory for telemetry JSON logs
    logs_dir = Path.cwd() / ".prompt_cache_logs"
    logs_dir.mkdir(exist_ok=True)

    # Anthropic via LiteLLM proxy, aligned with other examples in this repo
    llm = LLM(
        model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
        base_url="https://llm-proxy.eval.all-hands.dev",
        api_key=SecretStr(api_key),
        max_output_tokens=256,
        # Enable completion logging so we can inspect cache read/write tokens
        log_completions=True,
        log_completions_folder=str(logs_dir),
    )

    # Work around LiteLLM logging deepcopy issue by disabling LiteLLM internal logging
    try:
        litellm.set_verbose = True  # type: ignore[attr-defined]
    except Exception:
        pass

    agent = get_default_agent(llm=llm, working_dir=os.getcwd(), cli_mode=True)
    convo = Conversation(agent=agent)

    # Disable confirmation so tools execute without prompting
    convo.set_confirmation_policy(NeverConfirm())

    # Start time to filter newly written logs
    t0 = time.time()

    # Ask the agent to read README and summarize
    task = (
        "Please read the ./README.mdx file and provide a one-sentence summary.\n"
        "Use available tools to open and read files as needed."
    )
    print("\n▶️ Sending task to agent:", task)
    convo.send_message(task)

    # Drive until finished
    from openhands.sdk.conversation.state import AgentExecutionStatus

    while convo.state.agent_status != AgentExecutionStatus.FINISHED:
        convo.run()

    print("\n✅ Run complete. Inspecting telemetry logs in:", logs_dir)

    # Collect JSON logs generated after t0
    logs = sorted(
        [
            Path(p)
            for p in glob.glob(str(logs_dir / "*.json"))
            if os.path.getmtime(p) >= t0
        ]
    )

    if not logs:
        print("No telemetry logs found; ensure log directory exists and is writable.")
        return

    any_cache_read = False
    any_cache_write = False

    for p in logs:
        try:
            data = json.loads(Path(p).read_text())
        except Exception as e:
            print(f"  - {p.name}: failed to parse JSON: {e}")
            continue

        usage_summary = data.get("usage_summary", {})
        cache_read = int(usage_summary.get("cache_read_tokens", 0) or 0)
        prompt_tokens = int(usage_summary.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage_summary.get("completion_tokens", 0) or 0)

        # Also check cache creation tokens on providers that expose it
        cache_write = 0
        try:
            resp = data.get("response", {})
            usage = resp.get("usage") if isinstance(resp, dict) else None
            if usage and isinstance(usage, dict):
                cache_write = int(usage.get("_cache_creation_input_tokens", 0) or 0)
        except Exception:
            pass

        # Responses path indicator: raw_response is included for Responses API
        used_responses_api = "raw_response" in data

        any_cache_read |= cache_read > 0
        any_cache_write |= cache_write > 0

        print(
            "  -",
            p.name,
            f"transport={'responses' if used_responses_api else 'chat'}",
            f"prompt={prompt_tokens}",
            f"completion={completion_tokens}",
            f"cache_read={cache_read}",
            f"cache_write={cache_write}",
        )

    print("\nSummary:")
    print("  cache_read observed:", any_cache_read)
    print("  cache_write observed:", any_cache_write)
    if not any_cache_read:
        print(
            "  No cache reads observed; prompt caching may not be active on read paths."
        )


if __name__ == "__main__":
    main()
