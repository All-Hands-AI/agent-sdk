"""OpenHands Agent SDK — LLM Security Analyzer Example

This example shows how to use the LLMSecurityAnalyzer to automatically
evaluate security risks of actions before execution.
"""

import os

from pydantic import SecretStr

from openhands.sdk import LLM, Agent, Conversation, Message, TextContent
from openhands.sdk.security.llm_analyzer import LLMSecurityAnalyzer
from openhands.tools import BashTool, FileEditorTool


print("=== LLM Security Analyzer Example ===")

# Configure LLM
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."
llm = LLM(
    model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

# Tools
tools = [
    BashTool.create(working_dir=os.getcwd()),
    FileEditorTool.create(),
]

# Create agent with security analyzer
security_analyzer = LLMSecurityAnalyzer()
agent = Agent(llm=llm, tools=tools, security_analyzer=security_analyzer)
conversation = Conversation(agent=agent)

print("\n1) Safe command (LOW risk - should execute automatically)...")
conversation.send_message(
    Message(
        role="user",
        content=[TextContent(text="List files in the current directory")],
    )
)
conversation.run()

print("\n2) Potentially risky command (may require confirmation)...")
conversation.send_message(
    Message(
        role="user",
        content=[
            TextContent(text="Create a temporary file called 'security_test.txt'")
        ],
    )
)
conversation.run()

print("\n3) Cleanup...")
conversation.send_message(
    Message(
        role="user",
        content=[TextContent(text="Remove any test files created")],
    )
)
conversation.run()

print("\n=== Example Complete ===")
print("The LLMSecurityAnalyzer automatically evaluates action security risks.")
print(
    "HIGH risk actions require confirmation, while LOW risk actions execute directly."
)

security_analyzer.close()
