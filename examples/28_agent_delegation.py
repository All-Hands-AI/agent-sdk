"""
Agent Delegation Example

This example demonstrates the agent delegation feature where a main agent
delegates tasks to sub-agents for parallel processing.

The main agent receives a high-level programming task "Analyze this Python file for
quality."
The main agent decomposes the task into two parallel subtasks:
- Sub-agent 1: perform linting (detect style issues or naming problems)
- Sub-agent 2: perform complexity analysis (count functions or measure cyclomatic
  complexity)

Each sub-agent runs independently and returns its results to the main agent,
which then merges both analyses into a single consolidated report.
"""

import os
import tempfile

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Conversation,
    Event,
    LLMConvertibleEvent,
    get_logger,
)
from openhands.tools.preset.default import get_default_agent


logger = get_logger(__name__)

# Sample Python file to analyze
SAMPLE_PYTHON_CODE = '''
import os
import sys
from typing import List, Dict

def calculateSum(numbers):
    """Calculate sum of numbers"""
    total = 0
    for num in numbers:
        total += num
    return total

def process_data(data_list: List[Dict], filter_key: str = None):
    """Process a list of dictionaries"""
    results = []
    for item in data_list:
        if filter_key and filter_key not in item:
            continue
        processed_item = {}
        for key, value in item.items():
            if isinstance(value, str):
                processed_item[key] = value.upper()
            elif isinstance(value, (int, float)):
                processed_item[key] = value * 2
            else:
                processed_item[key] = value
        results.append(processed_item)
    return results

class DataProcessor:
    def __init__(self, config_file_path):
        self.config_file_path = config_file_path
        self.data = []

    def load_config(self):
        if not os.path.exists(self.config_file_path):
            raise FileNotFoundError(f"Config file not found: {self.config_file_path}")
        # Simulate config loading
        return {"setting1": "value1", "setting2": "value2"}

    def process_batch(self, batch_size=100):
        """Process data in batches"""
        for i in range(0, len(self.data), batch_size):
            batch = self.data[i:i+batch_size]
            yield process_data(batch)

def main():
    processor = DataProcessor("/path/to/config.json")
    try:
        config = processor.load_config()
        data = [{"name": "test", "value": 42}, {"name": "example", "value": 3.14}]
        processor.data = data

        for batch_result in processor.process_batch():
            print(f"Processed batch: {batch_result}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''

print("Agent Delegation Example")
print("This example demonstrates parallel task delegation between agents")
print()

# Configure LLM
api_key = os.getenv("LLM_API_KEY")
assert api_key is not None, "LLM_API_KEY environment variable is not set."
llm = LLM(
    model="litellm_proxy/anthropic/claude-sonnet-4-5-20250929",
    base_url="<secret_hidden>",
    api_key=SecretStr(api_key),
    service_id="agent",
    drop_params=True,
)

# Create a temporary Python file to analyze
with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
    f.write(SAMPLE_PYTHON_CODE)
    temp_file_path = f.name

try:
    print("🚀 Starting Agent Delegation Example")
    print("=" * 50)

    # Initialize main agent with delegation capabilities
    cwd = os.getcwd()
    main_agent = get_default_agent(llm=llm, enable_delegation=True, cli_mode=True)

    # Collect LLM messages for debugging
    llm_messages = []

    def conversation_callback(event: Event):
        if isinstance(event, LLMConvertibleEvent):
            llm_messages.append(event.to_llm_message())

    # Create conversation with the main agent
    conversation = Conversation(
        agent=main_agent,
        workspace=cwd,
        callbacks=[conversation_callback],
        visualize=True,
    )

    print(f"📁 Created temporary Python file: {temp_file_path}")
    print("🤖 Main agent will delegate analysis tasks to sub-agents")
    print()

    # Send the high-level task to the main agent
    task_message = (
        f"Please analyze the Python file at {temp_file_path} for code quality.\n\n"
        "I want you to delegate this work to two sub-agents working in parallel:\n"
        "1. Sub-agent 1: Perform linting analysis (style issues, naming problems, "
        "imports)\n"
        "2. Sub-agent 2: Perform complexity analysis (function count, complexity "
        "metrics)\n\n"
        "After both sub-agents complete their work, merge their analyses into a "
        "single consolidated report with recommendations.\n\n"
        "Use the delegation tool to spawn sub-agents, wait for their results, "
        "and then provide a comprehensive analysis."
    )

    print("📤 Sending task to main agent:")
    print(f"   {task_message[:100]}...")
    print()

    # Send message and run conversation
    conversation.send_message(task_message)
    conversation.run()

    print("✅ Agent delegation example completed!")
    print("📊 Check the conversation output above for the delegation workflow")
    print("=" * 100)

    print("Conversation finished. Got the following LLM messages:")
    for i, message in enumerate(llm_messages):
        print(f"Message {i}: {str(message)[:200]}")

finally:
    # Clean up temporary file
    if os.path.exists(temp_file_path):
        os.unlink(temp_file_path)
        print(f"🧹 Cleaned up temporary file: {temp_file_path}")
