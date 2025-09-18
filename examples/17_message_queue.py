"""
This example demonstrates the message queueing functionality in conversations.

When multiple messages are sent while an agent is busy, they are automatically
queued and processed sequentially after the current task completes.

This showcases:
1. Immediate processing when agent is idle
2. Automatic queueing when agent is busy
3. Sequential processing of queued messages
4. Queue status monitoring
"""

import os
import threading
import time

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    Event,
    LLMConvertibleEvent,
    Message,
    TextContent,
    get_logger,
)
from openhands.tools import BashTool, FileEditorTool, TaskTrackerTool


logger = get_logger(__name__)

# Configure LLM
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."
llm = LLM(
    model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

# Tools
cwd = os.getcwd()
tools = [
    BashTool.create(working_dir=cwd),
    FileEditorTool.create(),
    TaskTrackerTool.create(save_dir=cwd),
]

# Agent
agent = Agent(llm=llm, tools=tools)

# Track events and queue status
events = []
queue_statuses = []


def conversation_callback(event: Event):
    """Callback to track conversation events."""
    events.append(
        {
            "timestamp": time.time(),
            "event_type": type(event).__name__,
            "thread": threading.current_thread().name,
        }
    )
    if isinstance(event, LLMConvertibleEvent):
        logger.info(
            f"[{threading.current_thread().name}] Event: {type(event).__name__}"
        )


# Create conversation
conversation = Conversation(agent=agent, callbacks=[conversation_callback])

print("=" * 80)
print("MESSAGE QUEUEING DEMONSTRATION")
print("=" * 80)

# Demonstration 1: Single message (immediate processing)
print("\n1. SINGLE MESSAGE - IMMEDIATE PROCESSING")
print("-" * 50)

result1 = conversation.send_message_with_queue_status(
    Message(
        role="user",
        content=[
            TextContent(
                text="Create a file called demo1.txt with content 'Hello World'"
            )
        ],
    )
)

print(f"Message 1 result: {result1}")
queue_status = conversation.get_queue_status()
print(f"Queue status: {queue_status}")

# Run the conversation
print("Running conversation...")
conversation.run()

print("✓ First message completed")

# Demonstration 2: Multiple concurrent messages (queueing in action)
print("\n2. CONCURRENT MESSAGES - QUEUEING DEMONSTRATION")
print("-" * 50)


def send_message_in_thread(message_text: str, message_id: int):
    """Send a message from a separate thread."""
    print(f"[Thread-{message_id}] Sending: {message_text}")

    result = conversation.send_message_with_queue_status(
        Message(role="user", content=[TextContent(text=message_text)])
    )

    queue_statuses.append(
        {
            "message_id": message_id,
            "result": result,
            "queue_status": conversation.get_queue_status(),
            "timestamp": time.time(),
        }
    )

    print(f"[Thread-{message_id}] Result: {result}")


# Start the first message in main thread (this will make agent busy)
print("Starting long-running task...")
conversation.send_message_with_queue_status(
    Message(
        role="user",
        content=[
            TextContent(
                text=(
                    "Create three files: demo2.txt with 'File Two', "
                    "demo3.txt with 'File Three', "
                    "and demo4.txt with 'File Four'. "
                    "Take your time and use the task tracker."
                )
            )
        ],
    )
)


# Start the main task in a separate thread so we can send concurrent messages
def run_main_task():
    print("[Main-Task] Starting main conversation run...")
    conversation.run()
    print("[Main-Task] ✓ Main task completed")


main_task_thread = threading.Thread(target=run_main_task, name="Main-Task")
main_task_thread.start()

# Give the agent a moment to start processing
time.sleep(1)

# Now send multiple messages concurrently while agent is busy
print("Sending concurrent messages while agent is busy...")

message_threads = []
messages = [
    "List all .txt files in the current directory",
    "Check if demo1.txt exists and show its contents",
    "Create a summary file called summary.txt listing all created files",
    "Clean up by deleting all demo*.txt files",
]

# Send all messages concurrently
for i, msg in enumerate(messages, 2):  # Start from 2 since main task is 1
    thread = threading.Thread(
        target=send_message_in_thread, args=(msg, i), name=f"Thread-{i}"
    )
    message_threads.append(thread)
    thread.start()
    # Small delay to show the queueing effect
    time.sleep(0.1)

# Wait for all message threads to complete
for thread in message_threads:
    thread.join()

# Wait for main task to complete
main_task_thread.join()

print("\n3. QUEUE STATUS ANALYSIS")
print("-" * 50)

print("Queue status for each message:")
for status in queue_statuses:
    msg_id = status["message_id"]
    result = status["result"]
    queued = result.get("queued", False)
    queue_pos = result.get("queue_position", "N/A")
    agent_status = result.get("agent_status", "unknown")

    print(
        f"Message {msg_id}: {'QUEUED' if queued else 'IMMEDIATE'} "
        f"(Queue pos: {queue_pos}, Agent: {agent_status})"
    )

# Show final queue status
final_queue_status = conversation.get_queue_status()
print(f"\nFinal queue status: {final_queue_status}")

print("\n4. EVENT TIMELINE")
print("-" * 50)

# Show event timeline
start_time = events[0]["timestamp"] if events else time.time()
print("Event timeline (relative to start):")
for i, event in enumerate(events[:10]):  # Show first 10 events
    relative_time = event["timestamp"] - start_time
    print(f"  +{relative_time:.1f}s [{event['thread']}] {event['event_type']}")

if len(events) > 10:
    print(f"  ... and {len(events) - 10} more events")

print("\n" + "=" * 80)
print("DEMONSTRATION COMPLETE")
print("=" * 80)
print("Key observations:")
print("• First message processed immediately (agent was idle)")
print("• Subsequent messages were queued while agent was busy")
print("• Messages processed sequentially in FIFO order")
print("• Queue status provides real-time feedback")
print("• Thread-safe operation across multiple threads")
print("=" * 80)
