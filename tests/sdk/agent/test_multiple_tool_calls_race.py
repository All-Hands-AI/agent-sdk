"""
Test to replicate the race condition with multiple tool calls in final step.

This test replicates the exact scenario from the comprehensive test:
- Agent makes multiple tool calls in the same step (sleep + finish)
- Message is sent during the sleep execution
- This should cause the race condition where finish doesn't properly terminate
"""

import os
import threading
import time
from datetime import datetime
from unittest.mock import patch

from litellm import ChatCompletionMessageToolCall
from litellm.types.utils import (
    Choices,
    Function,
    Message as LiteLLMMessage,
    ModelResponse,
)

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
)
from openhands.sdk.tool import ToolSpec, register_tool
from openhands.tools.execute_bash import BashTool


def timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]  # Include milliseconds


# Track LLM calls
call_count = 0
test_start_time = time.time()


def mock_llm_completion(messages, **kwargs):
    """Mock LLM completion that returns both sleep and finish in same step"""
    global call_count
    call_count += 1

    elapsed = time.time() - test_start_time
    print(f"{elapsed:.3f} LLM Call #{call_count}")
    print(f"{elapsed:.3f} Messages in call: {len(messages)}")

    # Check if there's a race condition message in the conversation
    has_race_message = any(
        "race condition test message" in str(msg) for msg in messages
    )

    if has_race_message:
        print(
            f"{elapsed:.3f} ⚠️  RACE CONDITION DETECTED: "
            f"Extra message found in conversation!"
        )
        print(
            f"{elapsed:.3f} This means send_message() reset agent status "
            f"from FINISHED to IDLE"
        )
        print(
            f"{elapsed:.3f} The conversation should have terminated "
            f"but continued instead"
        )

        # Return a response that shows the race condition occurred
        return ModelResponse(
            id="race_condition_response",
            choices=[
                Choices(
                    message=LiteLLMMessage(
                        role="assistant",
                        content="I see the race condition test message - "
                        "this proves the bug exists!",
                    )
                )
            ],
            created=int(time.time()),
            model="gpt-4o",
            object="chat.completion",
        )

    # First call: Return both sleep and finish tool calls
    # (multiple tool calls in same step)
    sleep_call = ChatCompletionMessageToolCall(
        id="sleep_call_1",
        function=Function(
            name="execute_bash",
            arguments='{"command": "sleep 6"}',  # Increased for better race window
        ),
        type="function",
    )

    finish_call = ChatCompletionMessageToolCall(
        id="finish_call_1",
        function=Function(
            name="finish",
            arguments='{"message": "Task completed successfully"}',
        ),
        type="function",
    )

    return ModelResponse(
        id="multiple_tool_calls_response",
        choices=[
            Choices(
                message=LiteLLMMessage(
                    role="assistant",
                    content="I'll sleep for 3 seconds and then finish the task.",
                    tool_calls=[
                        sleep_call,
                        finish_call,
                    ],  # Multiple tool calls in same step!
                )
            )
        ],
        created=int(time.time()),
        model="gpt-4o",
        object="chat.completion",
    )


# Setup
register_tool("BashTool", BashTool)
tools = [
    ToolSpec(name="BashTool", params={"working_dir": os.getcwd()}),
]
llm = LLM(model="gpt-4o")
agent = Agent(llm=llm, tools=tools)
conversation = Conversation(agent, visualize=False)

# Track state
conversation_ended = False
message_sent = False


def send_race_condition_message():
    """Send a message during the sleep execution to trigger race condition"""
    global message_sent
    elapsed = time.time() - test_start_time
    print(f"{elapsed:.3f} Sending race condition test message")

    # Send message that should trigger race condition
    conversation.send_message(
        "This is a race condition test message - should trigger the bug"
    )
    message_sent = True

    elapsed = time.time() - test_start_time
    print(f"{elapsed:.3f} Race condition test message sent")


# Patch the LLM completion method
with patch("openhands.sdk.llm.LLM.completion", side_effect=mock_llm_completion):
    print("0.000 === Testing Multiple Tool Calls Race Condition ===")
    print("0.000 Sending initial message")

    # Send initial message to start the conversation
    conversation.send_message(
        "Please execute a task that involves both sleeping and finishing"
    )

    # Start conversation in background thread
    def run_conversation():
        """Run the conversation in a separate thread"""
        global conversation_ended
        elapsed = time.time() - test_start_time
        print(f"{elapsed:.3f} Starting conversation.run()")

        conversation.run()

        conversation_ended = True
        elapsed = time.time() - test_start_time
        print(f"{elapsed:.3f} Conversation.run() ended")

    conversation_thread = threading.Thread(target=run_conversation)
    conversation_thread.start()

    # Wait for the sleep to start, then send race condition message
    time.sleep(1.0)  # Reduced delay to send message earlier
    race_thread = threading.Thread(target=send_race_condition_message)
    race_thread.start()

    # Wait for everything to complete
    conversation_thread.join()
    race_thread.join()

elapsed = time.time() - test_start_time
print(f"\n{elapsed:.3f} === Multiple Tool Calls Race Condition Results ===")
print(f"Message sent: {message_sent}")
print(f"Conversation ended: {conversation_ended}")
print(f"Total LLM calls: {call_count}")

if call_count == 1:
    print("✓ Only one LLM call made (expected behavior)")
    print("✓ Race condition did NOT occur - finish action worked correctly")
    print("\n✓ No race condition detected in this run")
    print("  (Race condition may be timing-dependent)")
elif call_count == 2:
    print("⚠️  Two LLM calls made - RACE CONDITION DETECTED!")
    print("⚠️  The finish action did NOT properly terminate the conversation")
    print("⚠️  send_message() reset agent status from FINISHED to IDLE")
    print("\n❌ RACE CONDITION CONFIRMED!")
    print(
        "  Multiple tool calls + concurrent message = "
        "conversation continues unexpectedly"
    )
else:
    print(f"❓ Unexpected number of LLM calls: {call_count}")
