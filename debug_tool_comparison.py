#!/usr/bin/env python3

from openhands.sdk.tool.spec import ToolSpec
from openhands.sdk.agent import Agent
from openhands.sdk.llm import LLM
from pydantic import SecretStr

# Create two agents with different tools
tools1 = [
    ToolSpec(name="BashTool"),
    ToolSpec(name="FileEditorTool"),
]

tools2 = [
    ToolSpec(name="BashTool"),
]

llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm")

agent1 = Agent(llm=llm, tools=tools1)
agent2 = Agent(llm=llm, tools=tools2)

print("Agent1 tools:", agent1.tools)
print("Agent2 tools:", agent2.tools)

print("\nAgent1 model_dump:")
print(agent1.model_dump(exclude_none=True))

print("\nAgent2 model_dump:")
print(agent2.model_dump(exclude_none=True))

print("\nAre they equal?", agent1.model_dump(exclude_none=True) == agent2.model_dump(exclude_none=True))

# Test the specific comparison that should fail
try:
    agent2.resolve_diff_from_deserialized(agent1)
    print("ERROR: No exception raised!")
except ValueError as e:
    print(f"SUCCESS: Exception raised as expected: {e}")