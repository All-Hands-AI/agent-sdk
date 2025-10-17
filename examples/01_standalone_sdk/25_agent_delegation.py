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
from openhands.sdk.delegation.manager import DelegationManager
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
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
    service_id="agent",
    drop_params=True,
)

cwd = os.getcwd()

with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=cwd) as f:
    f.write(SAMPLE_PYTHON_CODE)
    temp_file_path = f.name

try:
    print("🚀 Starting Agent Delegation Example")
    print("=" * 50)

    # Initialize main agent with delegation capabilities
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
    )

    # Register the conversation with the singleton delegation manager
    # This allows the delegate tool to look up the parent conversation by ID
    delegation_manager = DelegationManager()
    delegation_manager.register_conversation(conversation)
    print("🔗 Registered parent conversation with DelegationManager")

    print(f"📁 Created temporary Python file: {temp_file_path}")
    print("🤖 Main agent will delegate analysis tasks to sub-agents")
    print("   Sub-agents will run as real conversations with full visualization")
    print()

    # Send the high-level task to the main agent
    task_message = (
        f"Please analyze the Python file at {temp_file_path} for code quality.\n\n"
        "I want you to delegate this work to two sub-agents working in parallel:\n"
        "1. Sub-agent 1: Perform a LIGHT linting analysis. Just identify 2 main "
        "style issues (like naming problems or unused imports). Keep it brief.\n"
        "2. Sub-agent 2: Perform a LIGHT complexity analysis. Just count the functions "
        "and identify the most complex one. Keep it brief.\n\n"
        "IMPORTANT: Tell each sub-agent to keep their analysis SHORT and CONCISE "
        "(no more than 10 lines of output each).\n\n"
        "Use the delegate tool to spawn both sub-agents with their tasks. "
        "After spawning them, use FinishAction to pause and wait for their results. "
        "The sub-agents will send their analysis back to you when complete.\n\n"
        "Once you receive results from BOTH sub-agents, merge their analyses into a "
        "single SHORT consolidated report (5-10 lines total) with top recommendations."
    )

    print("📤 Sending task to main agent:")
    print(f"   {task_message[:100]}...")
    print()

    # Send message and run conversation
    conversation.send_message(task_message)
    conversation.run()

    # Main agent will finish after spawning sub-agents
    # Sub-agents will automatically trigger the parent conversation to run
    # when they send messages back via the delegation manager
    #
    # Wait for all sub-agent threads to complete
    import time

    print("⏳ Waiting for sub-agent threads to complete...")
    print()

    # Get the delegation manager from the main agent's delegate tool
    delegation_tool = main_agent.tools_map.get("delegate")
    delegation_manager = None
    if delegation_tool is not None:
        try:
            executor = delegation_tool.as_executable().executor
            # DelegateExecutor exposes delegation_manager at runtime
            delegation_manager = getattr(executor, "delegation_manager", None)
        except Exception:
            delegation_manager = None

    # Wait for specific sub-agent threads to complete (with timeout)
    max_wait = 180  # 3 minutes to account for LLM processing time
    start_time = time.time()

    if delegation_manager:
        # Get the specific sub-agent threads we created
        sub_agent_threads = list(delegation_manager.sub_agent_threads.items())
        print(f"   Waiting for {len(sub_agent_threads)} sub-agent thread(s)...")

        for sub_conv_id, thread in sub_agent_threads:
            remaining = max_wait - (time.time() - start_time)
            if remaining <= 0:
                print(f"   ⏰ Timeout after {max_wait}s waiting for sub-agent threads")
                break

            # Wait for this specific thread to complete
            thread.join(timeout=remaining)

            if not thread.is_alive():
                print(f"   ✅ Sub-agent {sub_conv_id[:8]} thread completed")
            else:
                print(
                    f"   ⚠️  Sub-agent {sub_conv_id[:8]} thread still running after"
                    " timeout"
                )

        # Check if all threads completed
        all_completed = all(not thread.is_alive() for _, thread in sub_agent_threads)
        if all_completed:
            print("\n✅ All sub-agent threads completed successfully!")
        else:
            print(
                f"\n⏰ Timeout after {int(time.time() - start_time)}s - some threads"
                " still running"
            )

        # Also wait for parent conversation threads (triggered by sub-agent messages)
        parent_threads = delegation_manager.parent_threads.get(str(conversation.id), [])
        if parent_threads:
            print(
                f"\n⏳ Waiting for {len(parent_threads)} parent conversation "
                "thread(s)..."
            )
            for i, thread in enumerate(parent_threads):
                remaining = max_wait - (time.time() - start_time)
                if remaining <= 0:
                    print("   ⏰ Timeout waiting for parent threads")
                    break

                thread.join(timeout=remaining)
                if not thread.is_alive():
                    print(f"   ✅ Parent thread {i + 1} completed")
                else:
                    print(f"   ⚠️  Parent thread {i + 1} still running after timeout")

            all_parent_completed = all(not t.is_alive() for t in parent_threads)
            if all_parent_completed:
                print("✅ All parent conversation threads completed!")
            else:
                print("⚠️  Some parent threads still running")
    else:
        print("⚠️  No delegation manager found")

    print()

    # Verify that main agent received messages from both sub-agents
    print("🔍 Verifying delegation workflow...")
    sub_agent_message_count = sum(1 for msg in llm_messages if "[Sub-agent" in str(msg))
    print(f"   Found {sub_agent_message_count} messages from sub-agents")

    # Check for specific sub-agent responses
    linting_found = any("lint" in str(msg).lower() for msg in llm_messages)
    complexity_found = any("complex" in str(msg).lower() for msg in llm_messages)

    print(f"   Linting analysis received: {'✅' if linting_found else '❌'}")
    print(f"   Complexity analysis received: {'✅' if complexity_found else '❌'}")

    # Verify main agent created consolidated report
    consolidated_found = any(
        "consolidat" in str(msg).lower() or "merged" in str(msg).lower()
        for msg in llm_messages
    )
    print(f"   Consolidated report created: {'✅' if consolidated_found else '❌'}")

    print()

    # Assert that delegation workflow completed successfully
    assert sub_agent_message_count >= 2, (
        f"Expected at least 2 sub-agent messages, got {sub_agent_message_count}"
    )
    assert linting_found, "Linting analysis not found in conversation"
    assert complexity_found, "Complexity analysis not found in conversation"

    print("✅ Agent delegation example completed successfully!")
    print("📊 Check the conversation output above for the delegation workflow")
    print("=" * 100)

finally:
    # Clean up temporary file
    if os.path.exists(temp_file_path):
        os.unlink(temp_file_path)
        print(f"🧹 Cleaned up temporary file: {temp_file_path}")
