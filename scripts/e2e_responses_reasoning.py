import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    EventBase,
    LLMConvertibleEvent,
    Message,
    TextContent,
    get_logger,
)
from openhands.tools.execute_bash import BashTool


logger = get_logger(__name__)


def to_serializable(event: LLMConvertibleEvent) -> dict[str, Any]:
    # Rich.Text -> plain for JSON
    visualization = event.visualize.plain  # type: ignore[attr-defined]
    data: dict[str, Any] = {
        "kind": event.__class__.__name__,
        "source": event.source,
        "timestamp": event.timestamp,
        "visualize": visualization,
        "raw": event.model_dump(),
    }
    # Try to surface reasoning_content if present on event
    try:
        rc = getattr(event, "reasoning_content")
        if rc:
            data["reasoning_content"] = rc
    except Exception:
        pass
    return data


def main() -> None:
    api_key = os.getenv("LITELLM_API_KEY")
    assert api_key, "LITELLM_API_KEY is not set"

    # Pick a GPT-5-mini variant to trigger Responses API routing and reasoning
    model = os.getenv("MODEL", "litellm_proxy/openai/gpt-5-mini-2025-04-16")
    base_url = os.getenv("BASE_URL", "https://llm-proxy.eval.all-hands.dev")

    llm = LLM(model=model, base_url=base_url, api_key=SecretStr(api_key))

    # Tools: bash in current repo directory
    tools: Sequence[Any] = [BashTool.create(working_dir=os.getcwd())]

    agent = Agent(llm=llm, tools=tools)  # type: ignore[arg-type]

    events_out: list[dict[str, Any]] = []

    def cb(event: EventBase) -> None:
        if isinstance(event, LLMConvertibleEvent):
            events_out.append(to_serializable(event))
            # Also echo to console for quick inspection
            print(event.visualize)

    convo = Conversation(agent=agent, callbacks=[cb])

    # Prompt designed to elicit tool use and reasoning
    user_text = (
        "Read the README.mdx in this repository using the bash tool "
        "(e.g., view a snippet), summarize the first 50 lines concisely, then stop."
    )

    convo.send_message(
        message=Message(role="user", content=[TextContent(text=user_text)])
    )
    convo.run()

    # Save log
    log_dir = Path("logs/reasoning").resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_path = log_dir / f"run_{ts}.json"

    out = {
        "meta": {
            "model": llm.model,
            "base_url": llm.base_url,
            "timestamp": ts,
            "cwd": os.getcwd(),
        },
        "events": events_out,
    }
    out_path.write_text(json.dumps(out, indent=2))

    print("\nSaved reasoning log to:", out_path)


if __name__ == "__main__":
    main()
