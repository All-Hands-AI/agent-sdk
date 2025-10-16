#!/usr/bin/env python3
"""
TODO Agent for OpenHands Automated TODO Management

This script processes individual TODO(openhands) comments by:
1. Using OpenHands agent to implement the TODO (agent creates branch and PR)
2. Tracking the processing status and PR information for reporting

Usage:
    python agent.py <todo_json>

Arguments:
    todo_json: JSON string containing TODO information from scanner.py

Environment Variables:
    LLM_API_KEY: API key for the LLM (required)
    LLM_MODEL: Language model to use (default: openhands/claude-sonnet-4-5-20250929)
    LLM_BASE_URL: Optional base URL for LLM API
    GITHUB_TOKEN: GitHub token for creating PRs (required)
    GITHUB_REPOSITORY: Repository in format owner/repo (required)

For setup instructions and usage examples, see README.md in this directory.
"""

import argparse
import json
import os
import subprocess
import sys
import warnings

from prompt import PROMPT
from pydantic import SecretStr

from openhands.sdk import LLM, Conversation, get_logger
from openhands.tools.preset.default import get_default_agent


# Suppress Pydantic serialization warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
warnings.filterwarnings("ignore", message=".*PydanticSerializationUnexpectedValue.*")


logger = get_logger(__name__)


def run_git_command(cmd: list, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    logger.info(f"Running git command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    if check and result.returncode != 0:
        logger.error(f"Git command failed: {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stderr)

    return result


def get_current_branch() -> str:
    """Get the current git branch name."""
    result = run_git_command(["git", "branch", "--show-current"])
    return result.stdout.strip()


def find_pr_for_branch(branch_name: str) -> str | None:
    """
    Find the PR URL for a given branch using GitHub API.

    Args:
        branch_name: Name of the feature branch

    Returns:
        PR URL if found, None otherwise
    """
    logger.info(f"Looking for PR associated with branch: {branch_name}")

    # Get GitHub token from environment
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        logger.error("GITHUB_TOKEN environment variable not set")
        return None

    # Get repository info from git remote
    try:
        remote_result = run_git_command(["git", "remote", "get-url", "origin"])
        remote_url = remote_result.stdout.strip()

        # Extract owner/repo from remote URL
        import re

        match = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", remote_url)
        if not match:
            logger.error(f"Could not parse GitHub repo from remote URL: {remote_url}")
            return None

        owner, repo = match.groups()
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get git remote URL: {e}")
        return None

    # Search for PRs with this head branch
    api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    params = f"?head={owner}:{branch_name}&state=open"

    try:
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-H",
                f"Authorization: token {github_token}",
                "-H",
                "Accept: application/vnd.github.v3+json",
                f"{api_url}{params}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        prs = json.loads(result.stdout)

        if prs and len(prs) > 0:
            return prs[0]["html_url"]  # Return the first (should be only) PR
        else:
            logger.error(f"No open PR found for branch {branch_name}")
            return None

    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        logger.error(f"Failed to search for PR: {e}")
        return None


def process_todo(todo_data: dict) -> dict:
    """
    Process a single TODO item using OpenHands agent.

    Args:
        todo_data: Dictionary containing TODO information

    Returns:
        Dictionary containing processing results
    """
    file_path = todo_data["file"]
    line_num = todo_data["line"]
    description = todo_data["description"]
    todo_text = todo_data["text"]

    logger.info(f"Processing TODO in {file_path}:{line_num}")

    # Initialize result structure
    result = {
        "todo": todo_data,
        "status": "failed",
        "pr_url": None,
        "branch": None,
        "error": None,
    }

    try:
        # Check required environment variables
        required_env_vars = ["LLM_API_KEY", "GITHUB_TOKEN", "GITHUB_REPOSITORY"]
        for var in required_env_vars:
            if not os.getenv(var):
                error_msg = f"Required environment variable {var} is not set"
                logger.error(error_msg)
                result["error"] = error_msg
                return result

        # Set up LLM configuration
        api_key = os.getenv("LLM_API_KEY")
        if not api_key:
            error_msg = "LLM_API_KEY is required"
            logger.error(error_msg)
            result["error"] = error_msg
            return result

        llm_config = {
            "model": os.getenv("LLM_MODEL", "openhands/claude-sonnet-4-5-20250929"),
            "api_key": SecretStr(api_key),
        }

        if base_url := os.getenv("LLM_BASE_URL"):
            llm_config["base_url"] = base_url

        logger.info(f"Initializing LLM with model: {llm_config['model']}")
        if "base_url" in llm_config:
            logger.info(f"Using base URL: {llm_config['base_url']}")
        
        try:
            llm = LLM(**llm_config)
            logger.info("LLM initialized successfully")
        except Exception as e:
            error_msg = f"Failed to initialize LLM: {str(e)}"
            logger.error(error_msg)
            result["error"] = error_msg
            return result

        # Create the prompt
        prompt = PROMPT.format(
            file_path=file_path,
            line_num=line_num,
            description=description,
            todo_text=todo_text,
        )

        # Initialize agent and conversation
        agent = get_default_agent(llm=llm)
        conversation = Conversation(agent=agent)

        # Send the prompt to the agent
        logger.info("Sending TODO implementation request to agent")
        try:
            conversation.send_message(prompt)
            logger.info("Message sent successfully to agent")
        except Exception as e:
            error_msg = f"Failed to send message to agent: {str(e)}"
            logger.error(error_msg)
            result["error"] = error_msg
            return result

        # Store the initial branch (should be main)
        try:
            initial_branch = get_current_branch()
            logger.info(f"Initial branch: {initial_branch}")
        except Exception as e:
            logger.warning(f"Could not get initial branch: {str(e)}")
            initial_branch = "main"  # fallback

        # Run the agent
        logger.info("Running OpenHands agent to implement TODO...")
        try:
            conversation.run()
            logger.info("Agent execution completed")
        except Exception as e:
            error_msg = f"Agent execution failed: {str(e)}"
            logger.error(error_msg)
            result["error"] = error_msg
            return result

        # After agent runs, check if we're on a different branch (feature branch)
        current_branch = get_current_branch()
        logger.info(f"Current branch after agent run: {current_branch}")
        result["branch"] = current_branch

        if current_branch != initial_branch:
            # Agent created a feature branch, find the PR for it
            logger.info(f"Agent switched from {initial_branch} to {current_branch}")
            pr_url = find_pr_for_branch(current_branch)

            if pr_url:
                logger.info(f"Found PR URL: {pr_url}")
                result["pr_url"] = pr_url
                result["status"] = "success"
                logger.info(f"TODO processed successfully with PR: {pr_url}")
            else:
                logger.warning(f"Could not find PR for branch {current_branch}")
                result["status"] = "partial"  # Branch created but no PR found
        else:
            # Agent didn't create a feature branch, ask it to do so
            logger.info("Agent didn't create a feature branch, requesting one")
            follow_up = (
                "It looks like you haven't created a feature branch "
                "and pull request yet. "
                "Please create a feature branch for your changes and push them "
                "to create a pull request."
            )
            conversation.send_message(follow_up)
            conversation.run()

            # Check again for branch change
            current_branch = get_current_branch()
            result["branch"] = current_branch
            if current_branch != initial_branch:
                pr_url = find_pr_for_branch(current_branch)
                if pr_url:
                    logger.info(f"Found PR URL: {pr_url}")
                    result["pr_url"] = pr_url
                    result["status"] = "success"
                    logger.info(f"TODO processed successfully with PR: {pr_url}")
                else:
                    logger.warning(f"Could not find PR for branch {current_branch}")
                    result["status"] = "partial"  # Branch created but no PR found
            else:
                logger.warning("Agent still didn't create a feature branch")
                result["status"] = "failed"
                result["error"] = "Agent did not create a feature branch"

    except Exception as e:
        logger.error(f"Error processing TODO: {e}")
        result["error"] = str(e)
        result["status"] = "failed"

    return result


def main():
    """Main function to process a TODO item."""
    parser = argparse.ArgumentParser(
        description="Process a TODO(openhands) comment using OpenHands agent"
    )
    parser.add_argument("todo_json", help="JSON string containing TODO information")

    args = parser.parse_args()

    try:
        todo_data = json.loads(args.todo_json)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON input: {e}")
        sys.exit(1)

    # Validate required fields
    required_fields = ["file", "line", "description", "text"]
    for field in required_fields:
        if field not in todo_data:
            logger.error(f"Missing required field in TODO data: {field}")
            sys.exit(1)

    # Process the TODO and get results
    result = process_todo(todo_data)

    # Output result to a file for the workflow to collect
    result_file = (
        f"todo_result_{todo_data['file'].replace('/', '_')}_{todo_data['line']}.json"
    )
    with open(result_file, "w") as f:
        json.dump(result, f, indent=2)

    logger.info(f"Result written to {result_file}")
    logger.info(f"Processing result: {result['status']}")

    if result["status"] == "success":
        logger.info(f"PR URL: {result['pr_url']}")
    elif result["error"]:
        logger.error(f"Error: {result['error']}")

    # Exit with appropriate code
    if result["status"] == "failed":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
