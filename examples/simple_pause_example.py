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
    get_logger,
)
from openhands.tools import (
    BashTool,
    FileEditorTool,
)


logger = get_logger(__name__)

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

# Global flag to control the main loop
running = True


def signal_handler(signum, frame):
    """Handle Ctrl+C by pausing the conversation."""
    global running
    print("\n🛑 Pausing conversation...")
    conversation.pause()
    running = False


def run_agent():
    """Run the agent - this will be called in a background thread."""
    conversation.run()


def main():
    global running

    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    print("🚀 Simple pause example - Press Ctrl+C to pause")
    print("=" * 50)

    # Send a message to get the conversation started
    conversation.send_message(
        Message(role="user", content=[TextContent(text="Say hello to 'world'")])
    )

    # Start the agent in a background thread
    thread = threading.Thread(target=run_agent, daemon=True)
    thread.start()

    # Main loop - similar to the user's sample script
    while running and not conversation.state.agent_finished:
        # Send encouraging messages periodically
        if not conversation.state.agent_finished:
            conversation.send_message(
                Message(
                    role="user",
                    content=[TextContent(text="keep going! you can do it!")],
                )
            )
        time.sleep(1)

    # Wait for the thread to finish
    thread.join(timeout=2.0)

    if not running:
        print("🔄 Conversation paused! Press Enter to resume or Ctrl+C to exit...")
        try:
            input()
            print("▶️  Resuming...")
            running = True

            # Resume by calling run() again
            thread = threading.Thread(target=run_agent, daemon=True)
            thread.start()
            thread.join()

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            return

    print("✅ Conversation completed!")


if __name__ == "__main__":
    main()
