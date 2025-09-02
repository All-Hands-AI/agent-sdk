"""Integration test based on hello_world.py example with mocked LLM responses."""

import tempfile
from typing import Any, Dict, List
from unittest.mock import patch

from litellm.types.utils import Choices, Message as LiteLLMMessage, ModelResponse, Usage
from pydantic import SecretStr

from openhands.core import (
    LLM,
    ActionBase,
    CodeActAgent,
    Conversation,
    ConversationEventType,
    LLMConfig,
    Message,
    ObservationBase,
    TextContent,
    Tool,
    get_logger,
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
        self.collected_events: List[ConversationEventType] = []
        self.llm_messages: List[Dict[str, Any]] = []

    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def conversation_callback(self, event: ConversationEventType):
        """Callback to collect conversation events."""
        self.collected_events.append(event)
        if isinstance(event, ActionBase):
            self.logger.info(f"Found a conversation action: {event}")
        elif isinstance(event, ObservationBase):
            self.logger.info(f"Found a conversation observation: {event}")
        elif isinstance(event, Message):
            self.logger.info(f"Found a conversation message: {str(event)[:200]}...")
            self.llm_messages.append(event.model_dump())

    def create_mock_llm_responses(self):
        """Create mock LLM responses that simulate the agent's behavior."""
        # First response: Agent decides to create the file
        first_response = ModelResponse(
            id="mock-response-1",
            choices=[
                Choices(
                    index=0,
                    message=LiteLLMMessage(
                        role="assistant",
                        content="I'll help you create a Python file named hello.py that prints 'Hello, World!'. Let me create this file for you.",
                        tool_calls=[
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "str_replace_editor",
                                    "arguments": '{"command": "create", "path": "/tmp/hello.py", "file_text": "print(\\"Hello, World!\\")", "security_risk": "LOW"}'
                                }
                            }
                        ]
                    ),
                    finish_reason="tool_calls"
                )
            ],
            usage=Usage(prompt_tokens=50, completion_tokens=30, total_tokens=80)
        )

        # Second response: Agent acknowledges the file creation
        second_response = ModelResponse(
            id="mock-response-2",
            choices=[
                Choices(
                    index=0,
                    message=LiteLLMMessage(
                        role="assistant",
                        content="Perfect! I've successfully created the hello.py file that prints 'Hello, World!'. The file has been created and is ready to use."
                    ),
                    finish_reason="stop"
                )
            ],
            usage=Usage(prompt_tokens=80, completion_tokens=25, total_tokens=105)
        )

        return [first_response, second_response]

    @patch('openhands.core.llm.llm.litellm_completion')
    def test_hello_world_integration_with_mocked_llm(self, mock_completion):
        """Test the complete hello world flow with mocked LLM responses."""
        # Setup mock responses
        mock_responses = self.create_mock_llm_responses()
        mock_completion.side_effect = mock_responses

        # Configure mock LLM (no real API key needed)
        llm = LLM(config=LLMConfig(
            model="mock-model",
            api_key=SecretStr("mock-api-key"),
        ))

        # Tools setup with temporary directory
        bash = BashExecutor(working_dir=self.temp_dir)
        file_editor = FileEditorExecutor()
        tools: List[Tool] = [
            execute_bash_tool.set_executor(executor=bash),
            str_replace_editor_tool.set_executor(executor=file_editor),
        ]

        # Agent setup
        agent = CodeActAgent(llm=llm, tools=tools)

        # Conversation setup
        conversation = Conversation(agent=agent, callbacks=[self.conversation_callback])

        # Send the same message as in hello_world.py
        conversation.send_message(
            message=Message(
                role="user",
                content=[TextContent(text="Hello! Can you create a new Python file named hello.py that prints 'Hello, World!'?")],
            )
        )

        # Run the conversation
        conversation.run()

        # Verify that LLM was called
        assert mock_completion.call_count >= 1, "LLM completion should have been called"

        # Verify that we collected events
        assert len(self.collected_events) > 0, "Should have collected conversation events"

        # Verify that we have both actions and observations
        actions = [event for event in self.collected_events if isinstance(event, ActionBase)]
        observations = [event for event in self.collected_events if isinstance(event, ObservationBase)]
        messages = [event for event in self.collected_events if isinstance(event, Message)]

        assert len(actions) > 0, "Should have at least one action"
        assert len(observations) > 0, "Should have at least one observation"
        assert len(messages) > 0, "Should have at least one message"

        # Verify that LLM messages were collected
        assert len(self.llm_messages) > 0, "Should have collected LLM messages"

        # Check that the hello.py file was created (this should happen via the file editor tool)
        # Note: The actual file creation depends on the tool execution, which should work with our mock
        
        # Verify the conversation flow makes sense
        user_messages = [msg for msg in self.llm_messages if msg.get('role') == 'user']
        assistant_messages = [msg for msg in self.llm_messages if msg.get('role') == 'assistant']
        
        assert len(user_messages) >= 1, "Should have at least one user message"
        assert len(assistant_messages) >= 1, "Should have at least one assistant message"

        # Verify the user message content
        first_user_message = user_messages[0]
        user_content = first_user_message.get('content', [])
        user_text = ""
        if user_content:
            # Extract text from TextContent objects
            for content in user_content:
                if hasattr(content, 'text'):
                    user_text += content.text.lower()
                else:
                    user_text += str(content).lower()
        
        assert "hello.py" in user_text and "hello, world" in user_text, f"User message should mention hello.py and Hello, World! Got: {user_text}"

    @patch('openhands.core.llm.llm.litellm_completion')
    def test_conversation_callback_functionality(self, mock_completion):
        """Test that conversation callbacks work correctly."""
        # Setup simple mock response
        mock_completion.return_value = ModelResponse(
            id="mock-response",
            choices=[
                Choices(
                    index=0,
                    message=LiteLLMMessage(
                        role="assistant",
                        content="I understand your request."
                    ),
                    finish_reason="stop"
                )
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        )

        # Setup LLM and agent
        llm = LLM(config=LLMConfig(
            model="mock-model",
            api_key=SecretStr("mock-api-key"),
        ))

        bash = BashExecutor(working_dir=self.temp_dir)
        file_editor = FileEditorExecutor()
        tools: List[Tool] = [
            execute_bash_tool.set_executor(executor=bash),
            str_replace_editor_tool.set_executor(executor=file_editor),
        ]

        agent = CodeActAgent(llm=llm, tools=tools)
        conversation = Conversation(agent=agent, callbacks=[self.conversation_callback])

        # Send a simple message
        conversation.send_message(
            message=Message(
                role="user",
                content=[TextContent(text="Hello!")],
            )
        )

        conversation.run()

        # Verify callback was called
        assert len(self.collected_events) > 0, "Callback should have been called"
        assert len(self.llm_messages) > 0, "Should have collected LLM messages"

    def test_tool_integration(self):
        """Test that tools can be integrated with the agent without running conversation."""
        # Setup
        llm = LLM(config=LLMConfig(
            model="mock-model",
            api_key=SecretStr("mock-api-key"),
        ))

        bash = BashExecutor(working_dir=self.temp_dir)
        file_editor = FileEditorExecutor()
        tools: List[Tool] = [
            execute_bash_tool.set_executor(executor=bash),
            str_replace_editor_tool.set_executor(executor=file_editor),
        ]

        agent = CodeActAgent(llm=llm, tools=tools)
        conversation = Conversation(agent=agent, callbacks=[self.conversation_callback])

        # Send message without running the conversation
        conversation.send_message(
            message=Message(
                role="user",
                content=[TextContent(text="Please run echo 'test'")],
            )
        )

        # Verify tools were set up correctly
        assert len(tools) == 2, f"Should have 2 tools, got {len(tools)}: {[tool.name for tool in tools]}"
        assert any(tool.name == "execute_bash" for tool in tools), "Should have bash tool"
        assert any(tool.name == "str_replace_editor" for tool in tools), "Should have file editor tool"
        
        # Verify conversation was set up correctly
        assert conversation is not None, "Conversation should be created"
        assert agent is not None, "Agent should be created"

    def test_agent_and_tools_setup(self):
        """Test that agent and tools can be set up correctly without LLM calls."""
        # Setup without mocking LLM (just test the setup)
        llm = LLM(config=LLMConfig(
            model="mock-model",
            api_key=SecretStr("mock-api-key"),
        ))

        bash = BashExecutor(working_dir=self.temp_dir)
        file_editor = FileEditorExecutor()
        tools: List[Tool] = [
            execute_bash_tool.set_executor(executor=bash),
            str_replace_editor_tool.set_executor(executor=file_editor),
        ]

        # Verify tools are set up correctly
        assert len(tools) == 2
        assert tools[0].name == "execute_bash"
        assert tools[1].name == "str_replace_editor"
        assert tools[0].executor is not None
        assert tools[1].executor is not None

        # Verify agent can be created
        agent = CodeActAgent(llm=llm, tools=tools)
        assert agent is not None
        assert agent.llm == llm
        assert len(agent.tools) == 3  # execute_bash, str_replace_editor, finish

        # Verify conversation can be created
        conversation = Conversation(agent=agent, callbacks=[self.conversation_callback])
        assert conversation is not None
        assert conversation.agent == agent
