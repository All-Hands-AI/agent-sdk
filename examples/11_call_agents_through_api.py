import os

from pydantic import SecretStr

from openhands.sdk import LLM, OpenHandsClient, TextContent, ToolSpec


LLM_API_KEY = os.getenv("LITELLM_API_KEY")
if not LLM_API_KEY:
    raise RuntimeError("LITELLM_API_KEY environment variable is not set.")

with OpenHandsClient(server_url="http://localhost:9000", master_key="test") as oh:
    print("Starting conversation…")

    cwd = os.getcwd()
    conv_id, _state = oh.start_conversation(
        llm=LLM(
            model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
            api_key=SecretStr(LLM_API_KEY),
            base_url="https://llm-proxy.eval.all-hands.dev",
        ),
        tools=[
            ToolSpec(name="BashTool", params={"working_dir": cwd}),
            ToolSpec(name="FileEditorTool", params={}),
        ],
        mcp_config={
            "mcpServers": {"fetch": {"command": "uvx", "args": ["mcp-server-fetch"]}}
        },
    )
    print("Conversation ID:", conv_id)

    # 1) Ask the agent to read the repo and write 3 facts into FACTS.txt
    oh.send_message(
        conversation_id=conv_id,
        content=[
            TextContent(
                text="Read https://github.com/All-Hands-AI/OpenHands and "
                "write 3 facts about the project into FACTS.txt."
            )
        ],
    )
    oh.wait_until_idle(conv_id)

    # 2) Ask the agent to delete the file
    oh.send_message(
        conversation_id=conv_id,
        content=[TextContent(text="Great! Now delete that file.")],
    )
    oh.wait_until_idle(conv_id)

    # Print compact view of LLM messages
    print("=" * 80)
    evts = oh.get_events(conv_id, start=0, limit=1000)
    print("Events:")
    for e in evts:
        print(e)
