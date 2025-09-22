"""
Test demonstrating that messages sent during the final agent step are never processed.

This test demonstrates the bug where user messages sent while the agent is executing
its final action (that transitions to FINISHED state) are added to the events list
but never seen by the LLM because no subsequent step() call occurs.

The test uses a 3-step scenario with sleep tools to create controlled timing windows
for message injection, proving that:
1. Messages sent during non-final steps are processed in subsequent steps
2. Messages sent during the final step are never processed
"""

import threading
import time
from typing import TYPE_CHECKING
from unittest.mock import patch

from litellm import ChatCompletionMessageToolCall
from litellm.types.utils import (
    Choices,
    Function,
    Message as LiteLLMMessage,
    ModelResponse,
)
from pydantic import Field

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.event import MessageEvent
from openhands.sdk.llm import LLM, Message, TextContent
from openhands.sdk.tool import ActionBase, ObservationBase, Tool, ToolExecutor


if TYPE_CHECKING:
    from tests.sdk.agent.test_message_while_finishing import TestMessageWhileFinishing


# Custom sleep tool for testing timing scenarios
class SleepAction(ActionBase):
    duration: float = Field(description="Sleep duration in seconds")
    message: str = Field(description="Message to return after sleep")


class SleepObservation(ObservationBase):
    message: str = Field(description="Message returned after sleep")

    @property
    def agent_observation(self):
        from openhands.sdk.llm import TextContent

        return [TextContent(text=self.message)]


class SleepExecutor(ToolExecutor):
    test_start_time: float
    test_instance: "TestMessageWhileFinishing"

    def __call__(self, action: SleepAction) -> SleepObservation:
        start_time = time.time()
        elapsed = start_time - getattr(self, "test_start_time", start_time)
        print(
            f"[+{elapsed:.3f}s] Sleep action STARTED: "
            f"{action.duration}s - '{action.message}'"
        )

        # Track final step timing if this is the final sleep
        if hasattr(self, "test_instance") and "Final sleep" in action.message:
            self.test_instance.timestamps.append(("final_step_start", start_time))
            print(f"[+{elapsed:.3f}s] FINAL STEP STARTED")

        time.sleep(action.duration)

        end_time = time.time()
        actual_duration = end_time - start_time
        end_elapsed = end_time - getattr(self, "test_start_time", start_time)
        print(
            f"[+{end_elapsed:.3f}s] Sleep action COMPLETED: "
            f"{actual_duration:.3f}s actual - '{action.message}'"
        )

        # Track final step end timing
        if hasattr(self, "test_instance") and "Final sleep" in action.message:
            self.test_instance.timestamps.append(("final_step_end", end_time))
            print(f"[+{end_elapsed:.3f}s] FINAL STEP ENDED")

        return SleepObservation(message=action.message)


SLEEP_TOOL = Tool(
    name="sleep_tool",
    action_type=SleepAction,
    observation_type=SleepObservation,
    description="Sleep for specified duration and return a message",
    executor=SleepExecutor(),
)


class TestMessageWhileFinishing:
    """Test suite demonstrating the unprocessed message issue."""

    def setup_method(self):
        """Set up test fixtures."""
        self.llm = LLM(model="gpt-4")
        self.llm_completion_calls = []
        self.agent = Agent(llm=self.llm, tools=[SLEEP_TOOL])
        self.step_count = 0
        self.final_step_started = False
        self.timestamps = []  # Track key timing events

    def _mock_llm_response(self, messages, **kwargs):
        """
        Mock LLM that demonstrates the message processing bug through a 2-step scenario.
        """
        self.llm_completion_calls.append({"messages": messages, "kwargs": kwargs})
        self.step_count += 1
        elapsed = time.time() - self.test_start_time
        print(f"[+{elapsed:.3f}s] Step {self.step_count} LLM call")

        all_content = str(messages).lower()
        has_alligator = "alligator" in all_content
        has_butterfly = "butterfly" in all_content

        if self.step_count == 1:
            # Step 1: Process initial request - single sleep
            sleep_call = ChatCompletionMessageToolCall(
                id="sleep_call_1",
                type="function",
                function=Function(
                    name="sleep_tool",
                    arguments='{"duration": 2.0, "message": "First sleep completed"}',
                ),
            )
            return ModelResponse(
                id=f"response_step_{self.step_count}",
                choices=[
                    Choices(
                        message=LiteLLMMessage(
                            role="assistant",
                            content="I'll sleep for 2 seconds first",
                            tool_calls=[sleep_call],
                        )
                    )
                ],
                created=0,
                model="test-model",
                object="chat.completion",
            )

        else:
            # Step 2: Final step - sleep AND finish (multiple tool calls)
            self.final_step_started = True

            # Send butterfly message in a separate thread while we're still
            # in the LLM call
            def send_butterfly_now():
                time.sleep(
                    0.05
                )  # Give a tiny delay to ensure LLM response is processed
                elapsed = time.time() - self.test_start_time
                print(
                    f"[+{elapsed:.3f}s] Butterfly thread started from within "
                    "LLM response..."
                )

                # Check agent status - this should be RUNNING
                current_status = self.conversation.state.agent_status
                elapsed = time.time() - self.test_start_time
                print(
                    f"[+{elapsed:.3f}s] Agent status during LLM response: "
                    f"{current_status}"
                )

                # Send butterfly message regardless of status - this represents the user
                # sending a message during what they think is an ongoing operation
                butterfly_send_time = time.time()
                self.timestamps.append(("butterfly_sent", butterfly_send_time))
                elapsed = butterfly_send_time - self.test_start_time
                print(
                    f"[+{elapsed:.3f}s] BUTTERFLY MESSAGE SENT "
                    f"(status: {current_status})"
                )

                self.conversation.send_message(
                    Message(
                        role="user",
                        content=[
                            TextContent(
                                text="Please add the word 'butterfly' to your "
                                "next message"
                            )
                        ],
                    )
                )

            import threading

            butterfly_thread = threading.Thread(target=send_butterfly_now)
            butterfly_thread.start()

            response_content = "Now I'll sleep for a longer time and then finish"
            sleep_message = "Final sleep completed"
            final_message = "Task completed"

            if has_alligator:
                response_content += " with alligator"
                sleep_message += " with alligator"
                final_message += " with alligator"

            if has_butterfly:
                response_content += " and butterfly"
                sleep_message += " and butterfly"
                final_message += " and butterfly"  # This should NOT happen

            # Multiple tool calls: sleep THEN finish
            sleep_call = ChatCompletionMessageToolCall(
                id="sleep_call_2",
                type="function",
                function=Function(
                    name="sleep_tool",
                    arguments=f'{{"duration": 3.0, "message": "{sleep_message}"}}',
                ),
            )

            finish_call = ChatCompletionMessageToolCall(
                id="finish_call_2",
                type="function",
                function=Function(
                    name="finish",
                    arguments=f'{{"message": "{final_message}"}}',
                ),
            )

            return ModelResponse(
                id=f"response_step_{self.step_count}",
                choices=[
                    Choices(
                        message=LiteLLMMessage(
                            role="assistant",
                            content=response_content,
                            tool_calls=[sleep_call, finish_call],
                        )
                    )
                ],
                created=0,
                model="test-model",
                object="chat.completion",
            )

    def test_message_processing_bug_demonstration(self):
        """
        Demonstrates the bug: messages sent during final agent step are never processed.

        This test shows that when a user sends a message while the agent is executing
        its final action (that leads to FINISHED state), that message is added to the
        events list but never processed by the LLM because no subsequent step() call occurs.

        Timeline:
        1. Step 1: Agent sleeps for 2 seconds
        2. User sends "alligator" request during step 1 → Gets processed in step 2 ✓
        3. Step 2: Agent sleeps for 3 seconds AND finishes (final step with multiple actions)
        4. User sends "butterfly" request WHILE step 2 sleep is executing (agent still RUNNING) → Never processed ✗

        Key: The 3-second sleep creates a window to send butterfly while agent is still RUNNING.

        Expected: "alligator" appears in LLM calls and final result, "butterfly" does not.
        """  # noqa
        # Reset step count for this test
        self.step_count = 0
        self.llm_completion_calls = []
        self.final_step_started = False
        self.test_start_time = time.time()

        # Set the test start time reference for the sleep executor
        if SLEEP_TOOL.executor is not None:
            setattr(SLEEP_TOOL.executor, "test_start_time", self.test_start_time)
            # Pass test instance to executor for timestamp tracking
            setattr(SLEEP_TOOL.executor, "test_instance", self)

        conversation = Conversation(agent=self.agent)
        # Store conversation reference for use in mock LLM
        self.conversation = conversation

        def elapsed_time():
            return f"[+{time.time() - self.test_start_time:.3f}s]"

        print(f"{elapsed_time()} Test started")

        with patch(
            "openhands.sdk.llm.llm.litellm_completion",
            side_effect=self._mock_llm_response,
        ):
            # Start the conversation with a natural request
            print(f"{elapsed_time()} Sending initial message")
            conversation.send_message(
                Message(
                    role="user",
                    content=[
                        TextContent(
                            text="Please sleep for 2 seconds, then sleep for "
                            "3 seconds and finish"
                        )
                    ],
                )
            )

            # Run conversation in background thread
            print(f"{elapsed_time()} Starting conversation thread")
            thread = threading.Thread(target=conversation.run)
            thread.start()

            # Wait for step 1 to be processing (LLM call made, but not finished)
            print(f"{elapsed_time()} Waiting for step 1 to be processing...")
            while self.step_count < 1:
                time.sleep(0.1)

            print(
                f"{elapsed_time()} Sending alligator request during step 1 processing"
            )
            conversation.send_message(
                Message(
                    role="user",
                    content=[
                        TextContent(
                            text="Please add the word 'alligator' to your next message"
                        )
                    ],
                )
            )

            # The butterfly message is now sent from within the LLM response
            # Wait for conversation to complete
            print(f"{elapsed_time()} Waiting for conversation to complete...")

            # Wait for completion
            thread.join(timeout=10)

        # Debug: Print what we got
        print(f"\nDEBUG: Made {len(self.llm_completion_calls)} LLM calls")

        # The key insight: butterfly was sent during final step execution,
        # it should only appear in events but NEVER in any LLM call
        # because no subsequent step() occurs after the finish action

        # Check that both messages exist in the events list
        with conversation.state:
            message_events = [
                event
                for event in conversation.state.events
                if isinstance(event, MessageEvent) and event.llm_message.role == "user"
            ]

        user_messages = []
        for event in message_events:
            for content in event.llm_message.content:
                if isinstance(content, TextContent):
                    user_messages.append(content.text)

        assert "alligator" in str(user_messages), (
            "Alligator request message should be in events"
        )
        assert "butterfly" in str(user_messages), (
            "Butterfly request message should be in events"
        )

        # Verify that alligator request was processed (appears in LLM calls)
        alligator_seen = any(
            "alligator" in str(call["messages"]).lower()
            for call in self.llm_completion_calls
        )
        assert alligator_seen, "Alligator request should have been seen by LLM"

        # Verify that butterfly request was NOT processed (bug demonstration)
        butterfly_seen = any(
            "butterfly" in str(call["messages"]).lower()
            for call in self.llm_completion_calls
        )
        assert not butterfly_seen, (
            "Butterfly request should NOT have been seen by LLM. "
            "If this fails, the bug might be fixed or the test timing is wrong."
        )

        # TIMING ANALYSIS: Verify butterfly was sent during final step execution
        print("\nTIMING ANALYSIS:")

        # Extract timestamps
        timestamp_dict = dict(self.timestamps)
        if (
            "final_step_start" in timestamp_dict
            and "butterfly_sent" in timestamp_dict
            and "final_step_end" in timestamp_dict
        ):
            final_start = timestamp_dict["final_step_start"]
            butterfly_sent = timestamp_dict["butterfly_sent"]
            final_end = timestamp_dict["final_step_end"]

            print(f"- Final step started: [{final_start - self.test_start_time:.3f}s]")
            print(f"- Butterfly sent: [{butterfly_sent - self.test_start_time:.3f}s]")
            print(f"- Final step ended: [{final_end - self.test_start_time:.3f}s]")

            # CRITICAL ASSERTION: Butterfly message sent during final step execution
            assert final_start <= butterfly_sent <= final_end, (
                f"Butterfly message was NOT sent during final step execution! "
                f"Final step: {final_start:.3f}s-{final_end:.3f}s, "
                f"Butterfly sent: {butterfly_sent:.3f}s"
            )
            print("VERIFIED: Butterfly message was sent DURING final step execution")

            # Duration calculations
            step_duration = final_end - final_start
            butterfly_timing = butterfly_sent - final_start
            print(
                f"- Butterfly sent {butterfly_timing:.3f}s into "
                f"{step_duration:.3f}s final step"
            )
        else:
            print("WARNING: Missing timing data for analysis")
            print(f"Available timestamps: {list(timestamp_dict.keys())}")

        # Test has successfully demonstrated the bug behavior!
        print("\nTEST SUCCESSFULLY DEMONSTRATES THE BUG:")
        print("- Alligator request: sent during step 1 → processed in step 2")
        print(
            "- Butterfly request: sent during step 2 (final step execution) "
            "→ never processed"
        )
        print("- Both messages exist in events, but only alligator reached LLM")
        print(
            "- This proves: messages sent during final step execution "
            "are never processed"
        )
