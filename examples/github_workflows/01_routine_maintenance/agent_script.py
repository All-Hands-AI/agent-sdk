#!/usr/bin/env python3
"""
Example: Maintenance Task Runner

This example demonstrates how to run scheduled maintenance tasks with OpenHands
agent. The script accepts a prompt from a file or URL and runs the agent to
execute the maintenance task. It's designed to be used with GitHub Actions for
scheduled maintenance tasks.

Usage:
    python agent_script.py <prompt_location>

Arguments:
    prompt_location: Path to a local file or URL containing the prompt

Example prompts:
    - Check for outdated dependencies and create a PR to update them
    - Scan the repository for security vulnerabilities
    - Update documentation to match the latest code changes
    - Check for broken links in documentation
    - Run code quality checks and fix issues

Environment Variables:
    LLM_API_KEY: API key for the LLM (required)
                 Get one from https://docs.all-hands.dev/openhands/usage/llms/openhands-llms
    LLM_MODEL: Language model to use (default: openhands/claude-sonnet-4-5-20250929)
    LLM_BASE_URL: Optional base URL for LLM API

Local Testing:
    export LLM_API_KEY="your-api-key"
    export LLM_MODEL="openhands/claude-sonnet-4-5-20250929"
    echo "Check for outdated dependencies in requirements.txt" > prompt.txt
    python examples/github_workflows/01_routine_maintenance/agent_script.py prompt.txt

GitHub Actions:
    This script can be used with the workflow defined in workflow.yml to run
    scheduled maintenance tasks. Copy workflow.yml to .github/workflows/ in your
    repository and configure the required secrets.

    1. Set LLM_API_KEY secret in your repository settings
    2. Go to Actions → "Scheduled Maintenance Task"
    3. Click "Run workflow"
    4. Enter prompt location (URL or file path)
    5. Click "Run workflow"

    To enable scheduled runs, uncomment the schedule section in the workflow file.
"""

import argparse
import os
import sys
from urllib.parse import urlparse
from urllib.request import urlopen

from pydantic import SecretStr

from openhands.sdk import LLM, Conversation, Event, LLMConvertibleEvent, get_logger
from openhands.tools.preset.default import get_default_agent


logger = get_logger(__name__)


def is_url(path: str) -> bool:
    """Check if the given path is a URL."""
    try:
        result = urlparse(path)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def load_prompt(prompt_location: str) -> str:
    """
    Load prompt from a file or URL.

    Args:
        prompt_location: Path to a local file or URL containing the prompt

    Returns:
        The prompt content as a string

    Raises:
        ValueError: If the prompt cannot be loaded
    """
    try:
        if is_url(prompt_location):
            logger.info(f"Downloading prompt from URL: {prompt_location}")
            with urlopen(prompt_location) as response:
                return response.read().decode("utf-8")
        else:
            logger.info(f"Loading prompt from file: {prompt_location}")
            with open(prompt_location) as f:
                return f.read()
    except Exception as e:
        raise ValueError(f"Failed to load prompt from {prompt_location}: {e}")


def main():
    """Run the maintenance task with the provided prompt."""
    parser = argparse.ArgumentParser(
        description="Run OpenHands agent for maintenance tasks"
    )
    parser.add_argument(
        "prompt_location",
        help="Path to a local file or URL containing the prompt",
    )
    args = parser.parse_args()

    # Load the prompt
    try:
        prompt = load_prompt(args.prompt_location)
        logger.info(f"Loaded prompt ({len(prompt)} characters)")
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    # Configure LLM
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        logger.error("LLM_API_KEY environment variable is not set.")
        sys.exit(1)

    model = os.getenv("LLM_MODEL", "openhands/claude-sonnet-4-5-20250929")
    base_url = os.getenv("LLM_BASE_URL")

    llm_config = {
        "model": model,
        "api_key": SecretStr(api_key),
        "service_id": "maintenance_task",
        "drop_params": True,
    }

    if base_url:
        llm_config["base_url"] = base_url

    llm = LLM(**llm_config)

    # Get the current working directory as workspace
    cwd = os.getcwd()

    # Create agent with default tools
    agent = get_default_agent(
        llm=llm,
        cli_mode=True,
    )

    # Collect LLM messages for logging
    llm_messages = []

    def conversation_callback(event: Event):
        if isinstance(event, LLMConvertibleEvent):
            llm_messages.append(event.to_llm_message())

    # Create conversation
    conversation = Conversation(
        agent=agent,
        callbacks=[conversation_callback],
        workspace=cwd,
    )

    logger.info("Starting maintenance task execution...")
    logger.info(f"Prompt: {prompt[:200]}...")

    # Send the prompt and run the agent
    conversation.send_message(prompt)
    conversation.run()

    logger.info("Maintenance task completed successfully")
    logger.info(f"Total LLM messages: {len(llm_messages)}")


if __name__ == "__main__":
    main()
