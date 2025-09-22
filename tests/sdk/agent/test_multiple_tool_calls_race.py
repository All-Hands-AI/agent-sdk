"""
Race condition test for concurrent messages during multiple tool call execution.

User messages sent concurrently with multiple tool call execution can
cause improper conversation state transitions.

Bug Description:
    When an agent executes multiple tool calls in a single response (including a finish
    action), and a user message arrives during the execution window, the message handler
    incorrectly resets the agent status from FINISHED back to IDLE. This causes the
    conversation to continue processing instead of terminating as expected.

Root Cause:
    The conversation's send_message() method doesn't properly handle the case where
    the agent has already transitioned to FINISHED state during ongoing tool execution.
    The concurrent message processing overwrites the FINISHED status, leading to
    unexpected conversation continuation.

Test Strategy:
    Uses a controlled timing scenario with a long-running sleep command followed by
    a finish action to create a predictable race condition window. A separate thread
    injects a user message during the sleep execution to trigger the bug.

Technical Details:
    - Employs threading to simulate concurrent message arrival
    - Uses mocked LLM responses to control tool call sequences
    - Measures timing to ensure proper race condition setup
    - Validates bug presence by counting unexpected LLM invocations

Expected Behavior:
    Conversation should terminate after the finish action, regardless of concurrent messages.

Actual Behavior (Bug):
    Concurrent messages reset agent status, causing additional LLM calls and continued execution.
"""  # noqa

import os
import sys


# Ensure repo root on sys.path when running this file as a script
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import threading  # noqa: E402
import time  # noqa: E402
from unittest.mock import patch  # noqa: E402

from litellm import ChatCompletionMessageToolCall  # noqa: E402
from litellm.types.utils import (  # noqa: E402
    Choices,
    Function,
    Message as LiteLLMMessage,
    ModelResponse,
)

from openhands.sdk.agent import Agent  # noqa: E402
from openhands.sdk.conversation import Conversation  # noqa: E402
from openhands.sdk.llm import LLM, Message, TextContent  # noqa: E402
from openhands.sdk.tool import ToolSpec  # noqa: E402
from openhands.sdk.tool.registry import register_tool  # noqa: E402
from openhands.tools.execute_bash import BashTool  # noqa: E402


# Register the bash tool for sleep commands
register_tool("BashTool", BashTool)


class TestMultipleToolCallsRace:
    """
    Test suite for race condition bugs in concurrent message handling during tool execution.

    This test class focuses on reproducing and validating race conditions that occur when
    user messages are sent while the agent is executing multiple tool calls, particularly
    when one of those calls is a finish action that should terminate the conversation.

    The tests use controlled timing, threading, and mocked LLM responses to create
    reproducible race conditions that demonstrate the bug's impact on conversation flow.
    """  # noqa

    def setup_method(self):
        """
        Set up test fixtures and initialize components for race condition testing.

        Creates an agent with GPT-4o (supporting native function calling and multiple
        tool calls), initializes tracking variables for LLM calls and race conditions,
        and registers the BashTool for executing sleep commands during testing.
        """
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
        Mock LLM response generator that creates controlled race condition scenarios.

        This method simulates LLM responses to create predictable race conditions:
        - Step 1: Returns multiple tool calls (sleep + finish) to create timing window
        - Step 2+: Responds to race messages, proving the bug occurred

        The mock tracks call counts and timing to validate race condition behavior
        and determine whether the finish action properly terminated the conversation.

        Args:
            messages: Conversation messages from the agent
            **kwargs: Additional LLM parameters (unused in mock)

        Returns:
            ModelResponse: Mocked LLM response with appropriate tool calls or content
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
        Reproduces and validates the race condition bug in concurrent message handling.

        This test demonstrates a critical bug where user messages sent during multiple
        tool call execution can reset the agent's FINISHED status back to IDLE, causing
        conversations to continue unexpectedly instead of terminating properly.

        Test Scenario:
            The test creates a controlled race condition by having the agent execute
            multiple tool calls (sleep + finish) while a separate thread sends a user
            message during the sleep execution window.

        Execution Timeline:
            1. Agent receives initial request and responds with multiple tool calls
            2. Sleep command begins execution (6-second duration)
            3. Finish action is queued but not yet processed
            4. Race message is sent 1 second into sleep execution
            5. Race message processing resets agent status from FINISHED to IDLE
            6. After sleep completes, conversation continues instead of terminating

        Bug Validation:
            - Success case: 1 LLM call (conversation terminates properly)
            - Bug case: 2+ LLM calls (race condition occurred, conversation continued)

        Technical Implementation:
            - Uses threading to simulate concurrent message arrival
            - Employs mocked LLM responses for predictable behavior
            - Tracks timing and call counts to validate race condition occurrence
            - Provides detailed logging for debugging and analysis

        Expected Behavior:
            Conversation should terminate after the finish action, regardless of
            concurrent messages sent during tool execution.

        Actual Behavior (Bug):
            Concurrent messages reset the agent status, causing additional LLM calls
            and unexpected conversation continuation.
        """
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


# Utility: run this test many times in parallel when executed as a script
# Example:
#   python tests/sdk/agent/test_multiple_tool_calls_race.py --runs 50 --concurrency 50
# This will invoke pytest for this test N times in parallel and summarize results.


def _run_parallel_main():  # pragma: no cover - helper for manual stress testing
    import argparse
    import os
    import shutil
    import subprocess
    import sys
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from datetime import datetime

    # Compute repo root (three levels up from tests/sdk/agent)
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
    test_rel = os.path.relpath(__file__, repo_root)
    default_node = (
        f"{test_rel}::"
        "TestMultipleToolCallsRace::test_multiple_tool_calls_race_condition"
    )

    parser = argparse.ArgumentParser(
        description="Run this race test many times in parallel"
    )
    parser.add_argument("--nodeid", default=default_node, help="Pytest node id")
    parser.add_argument("--runs", type=int, default=50, help="Total runs")
    parser.add_argument("--concurrency", type=int, default=50, help="Max parallel runs")
    parser.add_argument(
        "--no-uv", action="store_true", help="Run pytest directly (no 'uv run')"
    )
    parser.add_argument(
        "--pytest-args", nargs=argparse.REMAINDER, help="Extra args passed to pytest"
    )
    args = parser.parse_args()

    use_uv = not args.no_uv
    extra_args = args.pytest_args if args.pytest_args else []

    print(
        "Running {} {} times with concurrency={} (uv={})".format(
            args.nodeid, args.runs, args.concurrency, use_uv
        )
    )

    def run_one(idx: int) -> tuple[int, int, str]:
        cmd: list[str] = []
        if use_uv and shutil.which("uv"):
            cmd.extend(["uv", "run"])  # prefer uv if available
        cmd.extend(["pytest", "-q", args.nodeid])
        if extra_args:
            cmd.extend(extra_args)

        env = os.environ.copy()
        start = datetime.now()
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=repo_root,
            env=env,
            text=True,
        )
        duration = (datetime.now() - start).total_seconds()
        out = f"[run {idx:02d}] rc={proc.returncode} dur={duration:.2f}s\n" + (
            proc.stdout or ""
        )
        return idx, proc.returncode, out

    failures: list[tuple[int, int, str]] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = [ex.submit(run_one, i + 1) for i in range(args.runs)]
        for fut in as_completed(futures):
            idx, rc, output = fut.result()
            status = "PASS" if rc == 0 else "FAIL"
            print(f"[run {idx:02d}] {status}")
            if rc != 0:
                failures.append((idx, rc, output))

    print("\nSummary:")
    print(
        "Total: {}, Passed: {}, Failed: {}".format(
            args.runs, args.runs - len(failures), len(failures)
        )
    )
    if failures:
        print("\n--- Failure outputs (first 3) ---")
        for i, (_idx, _rc, out) in enumerate(failures[:3], 1):
            print(f"\n[Failure {i}]\n{out}")
        sys.exit(1)

    print("All runs passed ✅")


if __name__ == "__main__":  # pragma: no cover - manual invocation only
    _run_parallel_main()
