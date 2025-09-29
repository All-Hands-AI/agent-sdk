#!/usr/bin/env python3

import tempfile
from openhands.sdk.tool.spec import ToolSpec
from openhands.sdk.agent import Agent
from openhands.sdk.llm import LLM, Message, TextContent
from pydantic import SecretStr
from openhands.sdk.conversation.impl.local_conversation import LocalConversation
from openhands.sdk import LocalFileStore
from openhands.sdk.tool import register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool

register_tool("BashTool", BashTool)
register_tool("FileEditorTool", FileEditorTool)

def test_debug():
    """Debug the failing test."""
    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = LocalFileStore(temp_dir)

        # Create and save conversation with original agent
        original_tools = [
            ToolSpec(name="BashTool"),
            ToolSpec(name="FileEditorTool"),
        ]
        llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm"
        )
        original_agent = Agent(llm=llm, tools=original_tools)
        
        print("Creating first conversation...")
        conversation = LocalConversation(
            agent=original_agent, working_dir=temp_dir, persist_filestore=file_store, visualize=False
        )

        # Send a message to create some state
        print("Sending message...")
        conversation.send_message(
            Message(role="user", content=[TextContent(text="test message")])
        )

        # Get the conversation ID for reuse
        conversation_id = conversation.state.id
        print(f"Conversation ID: {conversation_id}")

        # Delete conversation to simulate restart
        print("Deleting conversation...")
        del conversation

        # Try to create new conversation with different tools (only bash tool)
        different_tools = [
            ToolSpec(name="BashTool")
        ]  # Missing FileEditorTool
        llm2 = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm"
        )
        different_agent = Agent(llm=llm2, tools=different_tools)

        print("Creating second conversation with different agent...")
        print(f"Original agent tools: {original_agent.tools}")
        print(f"Different agent tools: {different_agent.tools}")
        
        # This should raise ValueError due to tool differences
        try:
            LocalConversation(
                agent=different_agent,
                working_dir=temp_dir,
                persist_filestore=file_store,
                conversation_id=conversation_id,  # Use same ID to avoid ID mismatch
                visualize=False,
            )
            print("ERROR: No exception raised!")
        except ValueError as e:
            print(f"SUCCESS: Exception raised as expected: {e}")

if __name__ == "__main__":
    test_debug()