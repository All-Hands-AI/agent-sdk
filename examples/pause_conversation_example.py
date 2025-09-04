import os
import signal
import threading
import time

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    LLMConfig,
    Message,
    TextContent,
)
from openhands.tools import (
    BashTool,
    FileEditorTool,
)


# Configure LLM
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."
llm = LLM(
    config=LLMConfig(
        model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
        base_url="https://llm-proxy.eval.all-hands.dev",
        api_key=SecretStr(api_key),
    )
)

# Tools
tools = [
    BashTool(working_dir=os.getcwd()),
    FileEditorTool(),
]

# Agent
agent = Agent(llm=llm, tools=tools)
conversation = Conversation(agent)

# Global flag to track if we should continue running
should_continue = True


def signal_handler(signum, frame):
    global should_continue
    print("\n🛑 Pausing conversation...")
    conversation.pause()
    should_continue = False


# Set up signal handler for Ctrl+C
signal.signal(signal.SIGINT, signal_handler)

print("Pause conversation example - Press Ctrl+C to pause")

# Send initial message to the agent
conversation.send_message(
    Message(
        role="user",
        content=[
            TextContent(
                text="Create a Python file that prints 'Hello, World!' and run it"
            )
        ],
    )
)

# Start agent in background thread
thread = threading.Thread(target=conversation.run, daemon=True)
thread.start()

# Monitor the conversation
while thread.is_alive() and should_continue:
    time.sleep(0.5)

# Wait for thread to finish if it's still alive
if thread.is_alive():
    thread.join(timeout=2.0)

if not should_continue:
    print("🔄 Conversation paused! Press Enter to resume...")
    try:
        input()
        print("▶️  Resuming...")
        should_continue = True

        # Resume by calling run() again
        thread = threading.Thread(target=conversation.run, daemon=True)
        thread.start()
        thread.join()

    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

print("✅ Conversation completed!")
