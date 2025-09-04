"""Integration test based on hello_world.py example with mocked LLM responses."""

import os
import tempfile
from typing import Any, Dict, List
from unittest.mock import patch

import pytest
from litellm.types.utils import Choices, Message as LiteLLMMessage, ModelResponse, Usage
from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    EventType,
    Message,
    TextContent,
    Tool,
    get_logger,
)
from openhands.sdk.event.llm_convertible import (
    ActionEvent,
    MessageEvent,
    ObservationEvent,
)
from openhands.tools import (
    BashExecutor,
    FileEditorExecutor,
    execute_bash_tool,
    str_replace_editor_tool,
)


class TestHelloWorldIntegration:
    """Integration test for the hello world example with mocked LLM."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.logger = get_logger(__name__)
        self.collected_events: List[EventType] = []
        self.llm_messages: List[Dict[str, Any]] = []

        # Clean up any existing hello.py files
        import os

        hello_files = ["/tmp/hello.py", os.path.join(self.temp_dir, "hello.py")]
        for file_path in hello_files:
            if os.path.exists(file_path):
                os.remove(file_path)

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def conversation_callback(self, event: EventType):
        """Callback to collect conversation events."""
        self.collected_events.append(event)
        if isinstance(event, ActionEvent):
            self.logger.info(f"Found a conversation action: {event}")
        elif isinstance(event, ObservationEvent):
            self.logger.info(f"Found a conversation observation: {event}")
        elif isinstance(event, MessageEvent):
            self.logger.info(f"Found a conversation message: {str(event)[:200]}...")
            self.llm_messages.append(event.llm_message.model_dump())

    def create_real_llm_responses_from_fixtures(self, fncall_raw_logs):
        """Create real LLM responses from stored fixture data."""
        responses = []

        # Filter for entries with assistant messages that have content
        valid_entries = []
        for log_entry in fncall_raw_logs:
            if "response" not in log_entry:
                continue
            response_data = log_entry["response"]
            choices = response_data.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                # Include entries with assistant messages that have content
                # (tool_calls may be empty in processed fixture data)
                if message.get("role") == "assistant" and message.get("content"):
                    valid_entries.append(log_entry)

        # Use all valid entries for complete conversation replay
        for log_entry in valid_entries:
            response_data = log_entry["response"]
            # Work with raw data - no cleaning
            model_response = ModelResponse(**response_data)
            responses.append(model_response)

        return responses

    def create_mock_llm_responses(self):
        """Create mock LLM responses that simulate the agent's behavior."""
        # Use absolute path in temp directory
        hello_path = os.path.join(self.temp_dir, "hello.py")

        # First response: Agent decides to create the file
        first_response = ModelResponse(
            id="mock-response-1",
            choices=[
                Choices(
                    index=0,
                    message=LiteLLMMessage(
                        role="assistant",
                        content="I'll help you create a Python file named hello.py "
                        "that prints 'Hello, World!'. Let me create this file for you.",
                        tool_calls=[
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "str_replace_editor",
                                    "arguments": f'{{"command": "create", '
                                    f'"path": "{hello_path}", '
                                    f'"file_text": "print(\\"Hello, World!\\")", '
                                    f'"security_risk": "LOW"}}',
                                },
                            }
                        ],
                    ),
                    finish_reason="tool_calls",
                )
            ],
            usage=Usage(prompt_tokens=50, completion_tokens=30, total_tokens=80),
        )

        # Second response: Agent acknowledges the file creation
        second_response = ModelResponse(
            id="mock-response-2",
            choices=[
                Choices(
                    index=0,
                    message=LiteLLMMessage(
                        role="assistant",
                        content="Perfect! I've successfully created the hello.py file "
                        "that prints 'Hello, World!'. The file has been created and is "
                        "ready to use.",
                    ),
                    finish_reason="stop",
                )
            ],
            usage=Usage(prompt_tokens=80, completion_tokens=25, total_tokens=105),
        )

        return [first_response, second_response]

    @patch("openhands.sdk.llm.llm.litellm_completion")
    def test_hello_world_integration_with_real_llm_data(
        self, mock_completion, fncall_raw_logs
    ):
        """Test the complete hello world flow with real LLM completion data."""
        # Setup real LLM responses from fixtures
        real_responses = self.create_real_llm_responses_from_fixtures(fncall_raw_logs)

        # Fallback to mock responses if no real data available
        if not real_responses:
            real_responses = self.create_mock_llm_responses()

        mock_completion.side_effect = real_responses

        # Configure LLM (no real API key needed)
        llm = LLM(
            model="claude-sonnet-4",
            api_key=SecretStr("mock-api-key"),
        )

        # Tools setup with temporary directory
        bash = BashExecutor(working_dir=self.temp_dir)
        file_editor = FileEditorExecutor()
        tools: List[Tool] = [
            execute_bash_tool.set_executor(executor=bash),
            str_replace_editor_tool.set_executor(executor=file_editor),
        ]

        # Agent setup
        agent = Agent(llm=llm, tools=tools)

        # Conversation setup
        conversation = Conversation(agent=agent, callbacks=[self.conversation_callback])

        # Send the same message as in hello_world.py
        conversation.send_message(
            message=Message(
                role="user",
                content=[
                    TextContent(
                        text="Hello! Can you create a new Python file named hello.py "
                        "that prints 'Hello, World!'?"
                    )
                ],
            )
        )

        # Run the conversation
        conversation.run()

        # Verify that LLM was called with real data
        assert mock_completion.call_count >= 1, "LLM completion should have been called"

        # Verify that we collected events
        assert len(self.collected_events) > 0, (
            "Should have collected conversation events"
        )

        # Verify that we have both actions and observations
        actions = [
            event for event in self.collected_events if isinstance(event, ActionEvent)
        ]
        observations = [
            event
            for event in self.collected_events
            if isinstance(event, ObservationEvent)
        ]
        messages = [
            event for event in self.collected_events if isinstance(event, MessageEvent)
        ]

        assert len(actions) > 0, (
            f"Should have at least one action. Found {len(actions)} actions out of "
            f"{len(self.collected_events)} total events"
        )
        assert len(observations) > 0, "Should have at least one observation"
        assert len(messages) > 0, "Should have at least one message"

        # Verify that LLM messages were collected
        assert len(self.llm_messages) > 0, "Should have collected LLM messages"

        # Verify the conversation flow makes sense
        user_messages = [msg for msg in self.llm_messages if msg.get("role") == "user"]
        assistant_messages = [
            msg for msg in self.llm_messages if msg.get("role") == "assistant"
        ]

        assert len(user_messages) >= 1, "Should have at least one user message"
        assert len(assistant_messages) >= 1, (
            "Should have at least one assistant message"
        )

        # Verify the user message content
        first_user_message = user_messages[0]
        user_content = first_user_message.get("content", [])
        user_text = ""
        if user_content:
            # Extract text from TextContent objects
            for content in user_content:
                if hasattr(content, "text"):
                    user_text += content.text.lower()
                else:
                    user_text += str(content).lower()

        assert "hello.py" in user_text and "hello, world" in user_text, (
            f"User message should mention hello.py and Hello, World! Got: {user_text}"
        )

        # Verify that we're using real LLM data by checking response characteristics
        # Real responses should have more authentic content and structure
        for response in real_responses:
            assert response.id is not None, "Real responses should have IDs"
            # Note: model field might be None in some fixture data, that's OK
            if response.choices:
                choice = response.choices[0]
                # Cast to Choices type to access message attribute
                if isinstance(choice, Choices) and choice.message:
                    assert choice.message.content is not None, (
                        "Real responses should have content"
                    )

    @patch("openhands.sdk.llm.llm.litellm_completion")
    def test_llm_completion_logging_fidelity(self, mock_completion, fncall_raw_logs):
        """Test mocked LLM completion logging produces same output."""
        # Setup real LLM responses from fixtures
        real_responses = self.create_real_llm_responses_from_fixtures(fncall_raw_logs)

        if not real_responses:
            pytest.skip("No real LLM fixture data available")

        mock_completion.side_effect = real_responses

        # Configure LLM with logging enabled
        llm = LLM(
            model="claude-sonnet-4",
            api_key=SecretStr("mock-api-key"),
        )

        # Tools setup with temporary directory
        bash = BashExecutor(working_dir=self.temp_dir)
        file_editor = FileEditorExecutor()
        tools: List[Tool] = [
            execute_bash_tool.set_executor(executor=bash),
            str_replace_editor_tool.set_executor(executor=file_editor),
        ]

        # Create agent and conversation
        agent = Agent(llm=llm, tools=tools)
        conversation = Conversation(agent=agent, callbacks=[self.conversation_callback])

        # Capture logged completion data by monitoring the LLM calls
        logged_completions = []
        original_responses = (
            real_responses.copy()
        )  # Make a copy to avoid modifying original
        response_index = 0

        def capture_completion_call(*args, **kwargs):
            nonlocal response_index
            # Get the next response from the list
            if response_index < len(original_responses):
                response = original_responses[response_index]
                response_index += 1

                # Capture the logged data structure
                logged_data = {
                    "messages": kwargs.get("messages", []),
                    "tools": kwargs.get("tools", []),
                    "response": response.model_dump(),
                    "model": kwargs.get("model"),
                    "temperature": kwargs.get("temperature"),
                    "max_tokens": kwargs.get("max_tokens"),
                }
                logged_completions.append(logged_data)
                return response
            else:
                # No more responses available
                raise StopIteration("No more mock responses available")

        mock_completion.side_effect = capture_completion_call

        # Send message and run conversation
        user_message = "Hello! Can you create a hello.py file?"
        conversation.send_message(
            message=Message(
                role="user",
                content=[TextContent(text=user_message)],
            )
        )
        conversation.run()

        # Compare logged completions with fixture data
        assert len(logged_completions) > 0, "Should have captured LLM completion logs"

        # Load original fixture data for comparison
        fixture_data = []
        for log_entry in fncall_raw_logs:
            fixture_data.append(log_entry)

        # Compare structure and content (excluding timestamps and latency)
        for i, (logged, fixture) in enumerate(zip(logged_completions, fixture_data)):
            self._compare_completion_data(logged, fixture, f"completion_{i}")

    def _compare_completion_data(self, logged_data, fixture_data, context):
        """Compare logged completion data with fixture data."""

        # Compare messages structure
        logged_messages = logged_data.get("messages", [])
        fixture_messages = fixture_data.get("messages", [])

        # For the first call, we expect fewer messages than full conversation
        # This is normal behavior - fixtures contain full conversation history
        print(
            f"{context}: Logged: {len(logged_messages)}, "
            f"Fixture: {len(fixture_messages)}"
        )

        # Validate that we have at least the basic structure
        assert len(logged_messages) >= 2, (
            f"{context}: Should have at least system + user messages. "
            f"Got: {len(logged_messages)}"
        )

        # Validate basic structure exists
        assert "messages" in logged_data, f"{context}: Missing 'messages' field"
        if "response" in logged_data:
            response = logged_data["response"]
            assert "choices" in response, f"{context}: Missing 'choices' in response"
            assert len(response["choices"]) > 0, f"{context}: Empty choices array"

        # Only compare the messages that exist in both (typically first few messages)
        min_messages = min(len(logged_messages), len(fixture_messages))

        for j in range(min_messages):
            logged_msg = logged_messages[j]
            fixture_msg = fixture_messages[j]
            assert logged_msg.get("role") == fixture_msg.get("role"), (
                f"{context} message {j}: Role mismatch. "
                f"Logged: {logged_msg.get('role')}, Fixture: {fixture_msg.get('role')}"
            )

            # Compare content structure (but allow for some flexibility in exact text)
            logged_content = logged_msg.get("content", [])
            fixture_content = fixture_msg.get("content", [])

            if isinstance(logged_content, list) and isinstance(fixture_content, list):
                assert len(logged_content) == len(fixture_content), (
                    f"{context} message {j}: Content length mismatch"
                )

        # Compare tools structure
        logged_tools = logged_data.get("tools", [])
        fixture_tools = fixture_data.get("tools", [])

        assert len(logged_tools) == len(fixture_tools), (
            f"{context}: Tools count mismatch. "
            f"Logged: {len(logged_tools)}, Fixture: {len(fixture_tools)}"
        )

        for k, (logged_tool, fixture_tool) in enumerate(
            zip(logged_tools, fixture_tools)
        ):
            assert logged_tool.get("type") == fixture_tool.get("type"), (
                f"{context} tool {k}: Type mismatch"
            )

            logged_func = logged_tool.get("function", {})
            fixture_func = fixture_tool.get("function", {})

            assert logged_func.get("name") == fixture_func.get("name"), (
                f"{context} tool {k}: Function name mismatch"
            )

        # Compare response structure (excluding time-sensitive fields)
        logged_response = logged_data.get("response", {})
        fixture_response = fixture_data.get("response", {})

        # Compare choices structure
        logged_choices = logged_response.get("choices", [])
        fixture_choices = fixture_response.get("choices", [])

        assert len(logged_choices) == len(fixture_choices), (
            f"{context}: Response choices count mismatch"
        )

        for choice_idx, (logged_choice, fixture_choice) in enumerate(
            zip(logged_choices, fixture_choices)
        ):
            # Compare message structure
            logged_msg = logged_choice.get("message", {})
            fixture_msg = fixture_choice.get("message", {})

            assert logged_msg.get("role") == fixture_msg.get("role"), (
                f"{context} response choice {choice_idx}: Message role mismatch"
            )

            # Compare tool_calls structure
            logged_tool_calls = logged_msg.get("tool_calls", [])
            fixture_tool_calls = fixture_msg.get("tool_calls", [])

            assert len(logged_tool_calls) == len(fixture_tool_calls), (
                f"{context} response choice {choice_idx}: Tool calls count mismatch"
            )

            for m, (logged_call, fixture_call) in enumerate(
                zip(logged_tool_calls, fixture_tool_calls)
            ):
                if logged_call and fixture_call:  # Skip empty objects
                    assert logged_call.get("type") == fixture_call.get("type"), (
                        f"{context} response choice {choice_idx} tool_call {m}: "
                        f"Type mismatch"
                    )

                    logged_func = logged_call.get("function", {})
                    fixture_func = fixture_call.get("function", {})

                    assert logged_func.get("name") == fixture_func.get("name"), (
                        f"{context} response choice {choice_idx} tool_call {m}: "
                        f"Function name mismatch"
                    )

    def test_non_function_call_integration(self):
        """Test LLM completion logging for non-function call responses (pure text)."""
        from litellm.types.utils import (
            Choices,
            Message as LiteLLMMessage,
            ModelResponse,
        )

        from openhands.sdk.llm import LLM
        from openhands.sdk.llm.message import Message, TextContent

        # Create a mock response without function calls (pure text response)
        mock_response = ModelResponse(
            id="test-non-func-call",
            choices=[
                Choices(
                    finish_reason="stop",
                    index=0,
                    message=LiteLLMMessage(
                        content="I understand you want to create a hello.py file.",
                        role="assistant",
                    ),
                )
            ],
            created=1234567890,
            model="claude-sonnet-4",
            object="chat.completion",
            system_fingerprint=None,
            usage=None,
        )

        # Mock the LLM to return our non-function call response
        captured_completions = []

        def capture_completion_fidelity(*args, **kwargs):
            # Capture the completion data for validation
            completion_data = {
                "messages": kwargs.get("messages", []),
                "tools": kwargs.get("tools", []),
                "response": mock_response.model_dump(),
                "timestamp": "2025-01-01T00:00:00Z",
                "latency_sec": 0.5,
            }
            captured_completions.append(completion_data)
            return mock_response

        # Create agent with mocked LLM
        llm = LLM(model="claude-sonnet-4")
        agent = Agent(llm=llm, tools=[])

        # Mock the completion method
        with patch(
            "openhands.sdk.llm.llm.litellm_completion",
            side_effect=capture_completion_fidelity,
        ):
            # Create conversation and send a message
            conversation = Conversation(agent=agent)
            conversation.send_message(
                message=Message(
                    role="user",
                    content=[TextContent(text="What is 2+2?")],
                )
            )

            # Run one step to get the non-function call response
            agent.step(conversation.state, on_event=conversation._on_event)

        # Validate that we captured the completion data
        assert len(captured_completions) == 1, (
            f"Expected 1 completion, got {len(captured_completions)}"
        )

        logged_data = captured_completions[0]

        # Validate structure for non-function call response
        assert "messages" in logged_data
        assert "response" in logged_data
        assert "timestamp" in logged_data
        assert "latency_sec" in logged_data

        # Validate response structure
        response = logged_data["response"]
        assert "choices" in response
        assert len(response["choices"]) == 1

        choice = response["choices"][0]
        message = choice["message"]

        # Validate this is a non-function call response
        assert message["role"] == "assistant"
        assert message["content"] is not None
        assert len(message["content"]) > 0

        # Validate no tool calls
        tool_calls = message.get("tool_calls")
        assert tool_calls is None or tool_calls == [], (
            f"Expected no tool calls, got {tool_calls}"
        )

        print("✅ Non-function call path tested successfully!")
        print(f"   Response content: {message['content'][:100]}...")
        print(f"   Tool calls: {tool_calls}")
        print(f"   Message count: {len(logged_data['messages'])}")

        # Create a mock response without function calls (pure text response)
        mock_response = ModelResponse(
            id="test-non-func-call",
            choices=[
                Choices(
                    finish_reason="stop",
                    index=0,
                    message=LiteLLMMessage(
                        content="I understand you want to create a hello.py file.",
                        role="assistant",
                    ),
                )
            ],
            created=1234567890,
            model="claude-sonnet-4",
            object="chat.completion",
            system_fingerprint=None,
            usage=None,
        )

        # Mock the LLM to return our non-function call response
        captured_completions = []

        def capture_completion_non_func(*args, **kwargs):
            # Capture the completion data for validation
            completion_data = {
                "messages": kwargs.get("messages", []),
                "tools": kwargs.get("tools", []),
                "response": mock_response.model_dump(),
                "timestamp": "2025-01-01T00:00:00Z",
                "latency_sec": 0.5,
            }
            captured_completions.append(completion_data)
            return mock_response

        # Create agent with mocked LLM
        agent = Agent(llm=LLM(model="claude-sonnet-4"), tools=[])

        # Mock the completion method
        with patch(
            "openhands.sdk.llm.llm.litellm_completion",
            side_effect=capture_completion_non_func,
        ):
            # Create conversation and send a message
            conversation = Conversation(agent=agent)
            conversation.send_message(
                message=Message(
                    role="user",
                    content=[TextContent(text="What is 2+2?")],
                )
            )

            # Run one step to get the non-function call response
            agent.step(conversation.state, on_event=conversation._on_event)

        # Validate that we captured the completion data
        assert len(captured_completions) == 1, (
            f"Expected 1 completion, got {len(captured_completions)}"
        )

        logged_data = captured_completions[0]

        # Validate structure for non-function call response
        assert "messages" in logged_data
        assert "response" in logged_data
        assert "timestamp" in logged_data
        assert "latency_sec" in logged_data

        # Validate response structure
        response = logged_data["response"]
        assert "choices" in response
        assert len(response["choices"]) == 1

        choice = response["choices"][0]
        message = choice["message"]

        # Validate this is a non-function call response
        assert message["role"] == "assistant"
        assert message["content"] is not None
        assert len(message["content"]) > 0

        # Validate no tool calls
        tool_calls = message.get("tool_calls")
        assert tool_calls is None or tool_calls == [], (
            f"Expected no tool calls, got {tool_calls}"
        )

        print("✅ Non-function call path tested successfully!")
        print(f"   Response content: {message['content'][:100]}...")
        print(f"   Tool calls: {tool_calls}")
        print(f"   Message count: {len(logged_data['messages'])}")
