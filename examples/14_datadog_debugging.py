#!/usr/bin/env python3
"""
Datadog Debugging Example

This example demonstrates how to use the OpenHands agent to debug errors
logged in Datadog.
The agent will:
1. Query Datadog logs to understand the error
2. Clone relevant GitHub repositories
3. Analyze the codebase to identify potential causes
4. Attempt to reproduce the error
5. Optionally create a draft PR with a fix

Usage:
    python 14_datadog_debugging.py --query "status:error service:deploy" \\
        --repos "All-Hands-AI/OpenHands,All-Hands-AI/deploy"

Environment Variables Required:
    - DATADOG_API_KEY: Your Datadog API key
    - DATADOG_APP_KEY: Your Datadog application key
    - GITHUB_TOKEN: Your GitHub personal access token
    - LITELLM_API_KEY: API key for the LLM service
"""

import argparse
import os
import sys
from pathlib import Path

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    Event,
    LLMConvertibleEvent,
    Message,
    TextContent,
    get_logger,
)
from openhands.tools import (
    BashTool,
    DatadogTool,
    FileEditorTool,
    GitHubTool,
    TaskTrackerTool,
)


logger = get_logger(__name__)


def validate_environment():
    """Validate that all required environment variables are set."""
    required_vars = [
        "DATADOG_API_KEY",
        "DATADOG_APP_KEY",
        "GITHUB_TOKEN",
        "LITELLM_API_KEY",
    ]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("\nPlease set the following environment variables:")
        for var in missing_vars:
            print(f"  export {var}=your_key_here")
        return False

    return True


def create_debugging_prompt(query: str, repos: list[str]) -> str:
    """Create the debugging prompt for the agent."""
    repos_list = "\n".join(f"- {repo}" for repo in repos)

    return (
        "Your task is to debug an error on Datadog to find out why it is "
        "happening. To read DataDog logs, you should interact with the "
        "datadog_search_logs tool using your DATADOG_API_KEY and "
        "DATADOG_APP_KEY environment variables.\n\n"
        "The Datadog API allows you to search logs using queries like:\n"
        "- status:error - Find error logs\n"
        "- service:my-service - Filter by service\n"
        '- "exact phrase" - Search for exact text\n'
        "- -(status:info OR status:debug) - Exclude certain statuses\n"
        "- Use time ranges to focus on recent issues\n\n"
        "The error class that I would like you to debug is characterized "
        f"by this datadog query:\n{query}\n\n"
        "The github repos that you should clone (using GITHUB_TOKEN) are "
        f"the following:\n{repos_list}\n\n"
        "The steps to debug are:\n"
        "1. Get an understanding of the error by reading the error messages "
        "from 3-5 instances found through the query.\n"
        "2. Check when the error class started occurring/becoming frequent "
        "to understand what code changes or release may have caused the "
        "changes. Keep in mind that all code that was changed during the "
        "release cycle before the error occurred will be the most "
        "suspicious.\n"
        "3. Carefully read the codebases included in repos that you "
        "downloaded and think carefully about the issue. Think of 5 "
        "possible reasons and test and see if you can write sample code "
        "that reproduces the error in any of them.\n"
        "4. If you are not able to reproduce the error message that you "
        "saw in the logs, finish right away and summarize your findings.\n"
        "5. If you were able to reproduce the error message that you saw "
        "in the logs, you can modify the code and open a draft PR that "
        "could fix the problem.\n\n"
        "Use the task_tracker tool to organize your work and keep track "
        "of your progress through these steps."
    )


def main():
    """Main function to run the Datadog debugging example."""
    parser = argparse.ArgumentParser(
        description="Debug errors from Datadog logs using OpenHands agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--query",
        required=True,
        help="Datadog query to search for error logs "
        "(e.g., 'status:error service:deploy')",
    )
    parser.add_argument(
        "--repos",
        required=True,
        help="Comma-separated list of GitHub repositories to analyze "
        "(e.g., 'All-Hands-AI/OpenHands,All-Hands-AI/deploy')",
    )
    parser.add_argument(
        "--working-dir",
        default="./datadog_debug_workspace",
        help="Working directory for cloning repos and analysis "
        "(default: ./datadog_debug_workspace)",
    )

    args = parser.parse_args()

    # Validate environment
    if not validate_environment():
        sys.exit(1)

    # Parse repositories
    repos = [repo.strip() for repo in args.repos.split(",")]

    # Create working directory
    working_dir = Path(args.working_dir).resolve()
    working_dir.mkdir(exist_ok=True)

    print("🔍 Starting Datadog debugging session")
    print(f"📊 Query: {args.query}")
    print(f"📁 Repositories: {', '.join(repos)}")
    print(f"💼 Working directory: {working_dir}")
    print()

    # Configure LLM
    api_key = os.getenv("LITELLM_API_KEY")
    if not api_key:
        print("❌ LITELLM_API_KEY environment variable is required")
        sys.exit(1)

    llm = LLM(
        model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
        base_url="https://llm-proxy.eval.all-hands.dev",
        api_key=SecretStr(api_key),
    )

    # Set up tools
    tools = [
        DatadogTool.create(),
        GitHubTool.create(working_dir=str(working_dir)),
        BashTool.create(working_dir=str(working_dir)),
        FileEditorTool.create(),
        TaskTrackerTool.create(save_dir=str(working_dir)),
    ]

    # Create agent
    agent = Agent(llm=llm, tools=tools)

    # Collect LLM messages for debugging
    llm_messages = []

    def conversation_callback(event: Event):
        if isinstance(event, LLMConvertibleEvent):
            llm_messages.append(event.to_llm_message())

    # Start conversation
    conversation = Conversation(agent=agent, callbacks=[conversation_callback])

    # Send the debugging task
    debugging_prompt = create_debugging_prompt(args.query, repos)

    conversation.send_message(
        message=Message(
            role="user",
            content=[TextContent(text=debugging_prompt)],
        )
    )

    print("🤖 Starting debugging analysis...")
    conversation.run()

    print("\n" + "=" * 80)
    print("🎯 Debugging session completed!")
    print(f"📁 Results saved in: {working_dir}")
    print(f"💬 Total LLM messages: {len(llm_messages)}")

    # Show summary of what was accomplished
    print("\n📋 Session Summary:")
    print("- Queried Datadog logs for error analysis")
    print("- Cloned and analyzed relevant repositories")
    print("- Investigated potential root causes")
    print("- Attempted error reproduction")

    if working_dir.exists():
        cloned_repos = [
            d for d in working_dir.iterdir() if d.is_dir() and (d / ".git").exists()
        ]
        if cloned_repos:
            print(f"- Cloned repositories: {', '.join(d.name for d in cloned_repos)}")


if __name__ == "__main__":
    main()
