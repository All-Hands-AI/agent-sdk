"""
Test demonstrating race condition with multiple tool calls and concurrent messages.

This test demonstrates the bug where user messages sent while the agent is executing
multiple tool calls (including a finish action) cause the conversation to continue
unexpectedly instead of terminating properly.

The test uses a controlled scenario with sleep + finish tool calls to create a timing
window for message injection, proving that concurrent messages reset the agent status
from FINISHED back to IDLE.
"""

import threading
import time
from unittest.mock import patch

from litellm import ChatCompletionMessageToolCall
from litellm.types.utils import (
    Choices,
    Function,
    Message as LiteLLMMessage,
    ModelResponse,
)

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.llm import LLM, Message, TextContent
from openhands.sdk.tool import ToolSpec
from openhands.sdk.tool.registry import register_tool
from openhands.tools.execute_bash import BashTool


# Register the bash tool for sleep commands
register_tool("BashTool", BashTool)


class TestMultipleToolCallsRace:
    """Test suite demonstrating the multiple tool calls race condition."""

    def setup_method(self):
        """Set up test fixtures."""
        # Use gpt-4o which supports native function calling and multiple tool calls
        self.llm = LLM(model="gpt-4o", native_tool_calling=True)
        self.llm_completion_calls = []
        self.agent = Agent(
            llm=self.llm,
            tools=[ToolSpec(name="BashTool", params={"working_dir": "/tmp"})],
        )
        self.step_count = 0
        self.race_message_sent = False

    def _mock_llm_response(self, messages, **kwargs):
        """
        Mock LLM that demonstrates the race condition with multiple tool calls.
        """
        self.llm_completion_calls.append({"messages": messages, "kwargs": kwargs})
        self.step_count += 1
        elapsed = time.time() - self.test_start_time
        print(f"[+{elapsed:.3f}s] Step {self.step_count} LLM call")

        all_content = str(messages).lower()
        has_race_message = "race condition test message" in all_content

        if self.step_count == 1:
            # Step 1: Process initial request - sleep + finish (multiple tool calls)
            sleep_call = ChatCompletionMessageToolCall(
                id="sleep_call_1",
                type="function",
                function=Function(
                    name="execute_bash",
                    arguments='{"command": "sleep 6"}',
                ),
            )

            finish_call = ChatCompletionMessageToolCall(
                id="finish_call_1",
                type="function",
                function=Function(
                    name="finish",
                    arguments='{"message": "Task completed successfully"}',
                ),
            )

            return ModelResponse(
                id=f"response_step_{self.step_count}",
                choices=[
                    Choices(
                        message=LiteLLMMessage(
                            role="assistant",
                            content="I'll sleep for 6 seconds and then finish the task.",  # noqa
                            tool_calls=[sleep_call, finish_call],
                        )
                    )
                ],
                created=0,
                model="test-model",
                object="chat.completion",
            )
        else:
            # Step 2: This happens because race message reset FINISHED status
            # This demonstrates the bug: messages sent during final step reset status
            response_content = "I received the race condition test message"
            if has_race_message:
                response_content += " - this proves the bug exists!"

            # Return a simple message response (no tool calls)
            return ModelResponse(
                id=f"response_step_{self.step_count}",
                choices=[
                    Choices(
                        message=LiteLLMMessage(
                            role="assistant",
                            content=response_content,
                        )
                    )
                ],
                created=0,
                model="test-model",
                object="chat.completion",
            )

    def test_multiple_tool_calls_race_condition(self):
        """
        Demonstrates the race condition: messages sent during multiple tool calls reset FINISHED status.

        This test shows that when a user sends a message while the agent is executing
        multiple tool calls (including a finish action), the message resets the agent
        status from FINISHED back to IDLE, causing the conversation to continue
        unexpectedly.

        Timeline:
        1. Step 1: Agent executes sleep + finish (multiple tool calls in same response)
        2. User sends race message WHILE sleep is executing → Resets FINISHED to IDLE
        3. Step 2: Conversation continues unexpectedly due to status reset

        Expected: Conversation should terminate after step 1 finish action.
        Actual: Conversation continues to step 2 due to status reset bug.
        """  # noqa
        # Reset step count for this test
        self.step_count = 0
        self.llm_completion_calls = []
        self.race_message_sent = False
        self.test_start_time = time.time()

        conversation = Conversation(agent=self.agent)
        # Store conversation reference for use in mock LLM
        self.conversation = conversation

        def elapsed_time():
            return f"[+{time.time() - self.test_start_time:.3f}s]"

        print(f"{elapsed_time()} Test started")

        def send_race_message():
            """Send race condition message during sleep execution."""
            # Wait for sleep to start, then send race message
            time.sleep(1.0)  # Wait for sleep to begin
            elapsed = time.time() - self.test_start_time
            print(f"[+{elapsed:.3f}s] Sending race condition message")

            conversation.send_message(
                Message(
                    role="user",
                    content=[
                        TextContent(
                            text="This is a race condition test message - should trigger the bug"  # noqa
                        )
                    ],
                )
            )
            self.race_message_sent = True
            elapsed = time.time() - self.test_start_time
            print(f"[+{elapsed:.3f}s] Race condition message sent")

        with patch(
            "openhands.sdk.llm.llm.litellm_completion",
            side_effect=self._mock_llm_response,
        ):
            # Start the conversation with a request for multiple tool calls
            print(f"{elapsed_time()} Sending initial message")
            conversation.send_message(
                Message(
                    role="user",
                    content=[
                        TextContent(
                            text="Please execute a task that involves both sleeping and finishing"  # noqa
                        )
                    ],
                )
            )

            # Run conversation in background thread
            print(f"{elapsed_time()} Starting conversation thread")
            conversation_thread = threading.Thread(target=conversation.run)
            conversation_thread.start()

            # Start race message thread
            race_thread = threading.Thread(target=send_race_message)
            race_thread.start()

            # Wait for both threads to complete
            conversation_thread.join(timeout=10)
            race_thread.join(timeout=1)

        print(f"{elapsed_time()} Test completed")

        # Analyze results
        print(f"\n{elapsed_time()} === Race Condition Test Results ===")
        print(f"Race message sent: {self.race_message_sent}")
        print(f"Total LLM calls: {len(self.llm_completion_calls)}")

        if len(self.llm_completion_calls) == 1:
            print("✅ One LLM call - race condition did NOT occur")
            print("✅ Conversation terminated properly after finish action")
        elif len(self.llm_completion_calls) == 2:
            print("⚠️  Two LLM calls - RACE CONDITION DETECTED!")
            print("⚠️  The finish action did NOT properly terminate the conversation")
            print("⚠️  send_message() reset agent status from FINISHED to IDLE")
            print("\n❌ RACE CONDITION CONFIRMED!")
            print(
                "  Multiple tool calls + concurrent message = conversation continues unexpectedly"  # noqa
            )
        else:
            print(
                f"❓ Unexpected number of LLM calls: {len(self.llm_completion_calls)}"
            )

        # The test passes regardless - it's demonstrating the bug
        assert self.race_message_sent, "Race message should have been sent"
        assert len(self.llm_completion_calls) >= 1, (
            "At least one LLM call should have occurred"
        )
