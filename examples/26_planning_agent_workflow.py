#!/usr/bin/env python3
"""
Planning Agent Workflow Example

This example demonstrates a two-stage workflow:
1. Planning Agent: Analyzes the task and creates a detailed implementation plan
2. Execution Agent: Implements the plan with full editing capabilities

The task: Create a Python web scraper that extracts article titles and URLs
from a news website, handles rate limiting, and saves results to JSON.
"""

import tempfile
from pathlib import Path

from pydantic import SecretStr

from openhands.sdk import LLM, Conversation
from openhands.sdk.llm import content_to_str
from openhands.tools.preset import get_planning_agent


def get_event_content(event):
    """Extract content from an event."""
    if hasattr(event, "llm_message"):
        return "".join(content_to_str(event.llm_message.content))
    return str(event)


def main():
    """Run the planning agent workflow example."""

    # Create a temporary workspace
    workspace_dir = Path(tempfile.mkdtemp())
    print(f"Working in: {workspace_dir}")

    # Initialize LLM (you'll need to set your API key)
    llm = LLM(
        model="gpt-4o-mini",
        api_key=SecretStr("your-api-key-here"),  # Replace with your actual API key
        service_id="openai",
    )

    # Task description
    task = """
    Create a Python web scraper with the following requirements:

    1. **Target**: Scrape article titles and URLs from a news website (e.g., BBC News)
    2. **Features**:
       - Extract article titles and their corresponding URLs
       - Implement proper rate limiting (1 request per second)
       - Handle HTTP errors gracefully with retry logic
       - Save results to a JSON file with timestamp
       - Include proper logging
       - Add command-line interface with argparse

    3. **Technical Requirements**:
       - Use requests and BeautifulSoup for scraping
       - Implement proper error handling and validation
       - Follow PEP 8 style guidelines
       - Include docstrings and type hints
       - Create a requirements.txt file
       - Add a simple README with usage instructions

    4. **Structure**:
       - Main scraper module
       - Configuration file for settings
       - Utility functions for common operations
       - Example usage script

    This is a moderately complex task that requires planning multiple components,
    handling external dependencies, and implementing proper software engineering
    practices.
    """

    print("=" * 80)
    print("PHASE 1: PLANNING")
    print("=" * 80)

    # Create Planning Agent with read-only tools
    planning_agent = get_planning_agent(llm=llm)

    # Create conversation for planning
    planning_conversation = Conversation(
        agent=planning_agent,
        workspace=str(workspace_dir),
    )

    # Run planning phase
    print("Planning Agent is analyzing the task and creating implementation plan...")
    planning_conversation.send_message(
        f"Please analyze this web scraping task and create a detailed "
        f"implementation plan:\n\n{task}"
    )
    planning_conversation.run()

    # Get the last message from the conversation
    planning_result = planning_conversation.state.events[-1]

    print("\n" + "=" * 80)
    print("PLANNING RESULT:")
    print("=" * 80)
    print(get_event_content(planning_result))

    print("\n" + "=" * 80)
    print("PHASE 2: EXECUTION")
    print("=" * 80)

    # Create Execution Agent with full editing capabilities
    from openhands.tools.preset.default import get_default_agent

    execution_agent = get_default_agent(llm=llm, cli_mode=True)

    # Create conversation for execution
    execution_conversation = Conversation(
        agent=execution_agent,
        workspace=str(workspace_dir),
    )

    # Prepare execution prompt with the plan
    execution_prompt = f"""
    Based on the following implementation plan, please implement the web scraper
    project:

    IMPLEMENTATION PLAN:
    {get_event_content(planning_result)}

    ORIGINAL TASK:
    {task}

    Please implement all the components according to the plan. Create all necessary
    files, implement the functionality, and ensure everything works together properly.
    """

    print("Execution Agent is implementing the plan...")
    execution_conversation.send_message(execution_prompt)
    execution_conversation.run()

    # Get the last message from the conversation
    execution_result = execution_conversation.state.events[-1]

    print("\n" + "=" * 80)
    print("EXECUTION RESULT:")
    print("=" * 80)
    print(get_event_content(execution_result))

    print("\n" + "=" * 80)
    print("WORKFLOW COMPLETE")
    print("=" * 80)
    print(f"Project files created in: {workspace_dir}")

    # List created files
    print("\nCreated files:")
    for file_path in workspace_dir.rglob("*"):
        if file_path.is_file():
            print(f"  - {file_path.relative_to(workspace_dir)}")


if __name__ == "__main__":
    print("Planning Agent Workflow Example")
    print("This example demonstrates a two-stage development workflow.")
    print("Make sure to set your API key in the script before running.")
    print()

    # Check if user wants to proceed
    response = input("Do you want to run the example? (y/N): ")
    if response.lower() in ["y", "yes"]:
        main()
    else:
        print("Example cancelled. Update the API key and run again when ready.")
