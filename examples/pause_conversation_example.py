import os
import signal
import threading
import time

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    EventType,
    LLMConfig,
    LLMConvertibleEvent,
    Message,
    TextContent,
    Tool,
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
cwd = os.getcwd()
tools: list[Tool] = [
    BashTool(working_dir=cwd),
    FileEditorTool(),
]

# Agent
agent = Agent(llm=llm, tools=tools)

llm_messages = []  # collect raw LLM messages


def conversation_callback(event: EventType):
    logger.info(f"Found a conversation message: {str(event)[:200]}...")
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


conversation = Conversation(agent=agent, callbacks=[conversation_callback])

# Global flag to track if we should continue running
should_continue = True
agent_thread = None


def signal_handler(signum, frame):
    """Handle Ctrl+C by pausing the conversation."""
    global should_continue
    print("\n🛑 Keyboard interrupt detected! Pausing conversation...")
    conversation.pause()
    should_continue = False


def run_agent():
    """Run the agent in a background thread."""
    try:
        conversation.run()
        print("✅ Agent finished execution")
    except Exception as e:
        print(f"❌ Agent encountered an error: {e}")


def main():
    global agent_thread, should_continue

    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    print("🚀 Starting pause conversation example...")
    print("💡 Press Ctrl+C at any time to pause the conversation")
    print("=" * 60)

    # Send initial message to the agent
    conversation.send_message(
        message=Message(
            role="user",
            content=[
                TextContent(
                    text=(
                        "Hello! Please help me with a few tasks:\n"
                        "1. Create a Python file that counts from 1 to 10\n"
                        "2. Run the file to show the output\n"
                        "3. Create another file that prints the current date and time\n"
                        "4. List all Python files in the current directory\n"
                        "Take your time with each step and be thorough."
                    )
                )
            ],
        )
    )

    # Start agent in background thread
    agent_thread = threading.Thread(target=run_agent, daemon=True)
    agent_thread.start()

    # Monitor the conversation
    try:
        while agent_thread.is_alive() and should_continue:
            time.sleep(0.5)  # Check every 500ms

            # Check if agent is still working
            if not conversation.state.agent_finished and should_continue:
                # Optionally send encouraging messages (like in the user's sample)
                # Uncomment the lines below if you want periodic encouragement
                # print("🔄 Agent is working...")
                pass

        # Wait for thread to finish if it's still alive
        if agent_thread.is_alive():
            print("⏳ Waiting for agent to pause...")
            agent_thread.join(timeout=5.0)  # Wait up to 5 seconds

        if not should_continue:
            print("\n🔄 Conversation paused! You can:")
            print("   1. Press Enter to resume")
            print("   2. Press Ctrl+C again to exit")

            try:
                input()  # Wait for user input
                print("▶️  Resuming conversation...")
                should_continue = True

                # Resume by calling run() again
                agent_thread = threading.Thread(target=run_agent, daemon=True)
                agent_thread.start()

                # Wait for completion
                while agent_thread.is_alive() and should_continue:
                    time.sleep(0.5)

                if agent_thread.is_alive():
                    agent_thread.join(timeout=5.0)

            except KeyboardInterrupt:
                print("\n👋 Exiting...")
                return

    except KeyboardInterrupt:
        print("\n👋 Exiting...")
        return

    print("\n" + "=" * 60)
    print("🎉 Conversation finished!")
    print(f"📊 Collected {len(llm_messages)} LLM messages")

    # Show summary of messages
    if llm_messages:
        print("\n📝 LLM Message Summary:")
        for i, message in enumerate(llm_messages[:3]):  # Show first 3 messages
            print(f"   Message {i + 1}: {str(message)[:100]}...")
        if len(llm_messages) > 3:
            print(f"   ... and {len(llm_messages) - 3} more messages")


if __name__ == "__main__":
    main()
