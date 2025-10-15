#!/usr/bin/env python3
"""
Example: PR Review Agent

This script runs OpenHands agent to review a pull request and provide
fine-grained review comments. It analyzes the PR diff, understands the
changes in context, and posts detailed review feedback.

Designed for use with GitHub Actions workflows triggered by PR labels.

Environment Variables:
    LLM_API_KEY: API key for the LLM (required)
    LLM_MODEL: Language model to use (default: openhands/claude-sonnet-4-5-20250929)
    LLM_BASE_URL: Optional base URL for LLM API
    GITHUB_TOKEN: GitHub token for API access (required)
    PR_NUMBER: Pull request number (required)
    PR_TITLE: Pull request title (required)
    PR_BODY: Pull request body (optional)
    PR_BASE_SHA: Base commit SHA (required)
    PR_HEAD_SHA: Head commit SHA (required)
    REPO_NAME: Repository name in format owner/repo (required)

For setup instructions, usage examples, and GitHub Actions integration,
see README.md in this directory.
"""

import json
import os
import subprocess
import sys
from typing import Dict, List, Optional

from pydantic import SecretStr

from openhands.sdk import LLM, Conversation, get_logger
from openhands.tools.preset.default import get_default_agent


logger = get_logger(__name__)


def get_pr_diff() -> str:
    """
    Get the diff for the current PR using git.
    
    Returns:
        The PR diff as a string
        
    Raises:
        RuntimeError: If unable to get the diff
    """
    try:
        # Get the diff between base and head
        base_sha = os.getenv("PR_BASE_SHA")
        head_sha = os.getenv("PR_HEAD_SHA")
        
        if not base_sha or not head_sha:
            raise RuntimeError("PR_BASE_SHA and PR_HEAD_SHA must be set")
            
        logger.info(f"Getting diff between {base_sha} and {head_sha}")
        
        # Use git diff to get the changes
        result = subprocess.run(
            ["git", "diff", f"{base_sha}...{head_sha}"],
            capture_output=True,
            text=True,
            check=True
        )
        
        diff_content = result.stdout
        if not diff_content.strip():
            logger.warning("No diff content found")
            return "No changes detected in this PR."
            
        logger.info(f"Retrieved diff with {len(diff_content)} characters")
        return diff_content
        
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to get PR diff: {e}")
    except Exception as e:
        raise RuntimeError(f"Error getting PR diff: {e}")


def post_review_comment(review_content: str) -> None:
    """
    Post a review comment to the PR using GitHub CLI.
    
    Args:
        review_content: The review content to post
    """
    try:
        pr_number = os.getenv("PR_NUMBER")
        repo_name = os.getenv("REPO_NAME")
        
        if not pr_number or not repo_name:
            raise RuntimeError("PR_NUMBER and REPO_NAME must be set")
            
        logger.info(f"Posting review comment to PR #{pr_number} in {repo_name}")
        
        # Use GitHub CLI to post the review
        subprocess.run(
            [
                "gh", "pr", "review", pr_number,
                "--repo", repo_name,
                "--comment",
                "--body", review_content
            ],
            check=True,
            env={**os.environ, "GH_TOKEN": os.getenv("GITHUB_TOKEN", "")}
        )
        
        logger.info("Successfully posted review comment")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to post review comment: {e}")
        raise RuntimeError(f"Failed to post review comment: {e}")
    except Exception as e:
        logger.error(f"Error posting review comment: {e}")
        raise RuntimeError(f"Error posting review comment: {e}")


def create_review_prompt(pr_info: Dict[str, str], diff_content: str) -> str:
    """
    Create a comprehensive prompt for PR review.
    
    Args:
        pr_info: Dictionary containing PR information
        diff_content: The PR diff content
        
    Returns:
        A formatted prompt for the review agent
    """
    prompt = f"""You are an expert code reviewer. Please provide a thorough and constructive review of this pull request.

## Pull Request Information
- **Title**: {pr_info.get('title', 'N/A')}
- **Description**: {pr_info.get('body', 'No description provided')}
- **Repository**: {pr_info.get('repo_name', 'N/A')}

## Your Review Task
Please analyze the following code changes and provide:

1. **Overall Assessment**: A high-level summary of the changes and their impact
2. **Code Quality**: Comments on code structure, readability, and best practices
3. **Potential Issues**: Any bugs, security concerns, or performance issues you identify
4. **Suggestions**: Specific recommendations for improvement
5. **Positive Feedback**: Highlight good practices and well-implemented features

## Guidelines for Your Review
- Be constructive and helpful in your feedback
- Focus on significant issues rather than minor style preferences
- Consider the broader context and impact of changes
- Suggest specific improvements where possible
- Acknowledge good practices when you see them

## Code Changes to Review

```diff
{diff_content}
```

Please provide your review in a clear, well-structured format that will be helpful to the PR author and other reviewers.
"""
    return prompt


def main():
    """Run the PR review agent."""
    logger.info("Starting PR review process...")
    
    # Validate required environment variables
    required_vars = [
        "LLM_API_KEY", "GITHUB_TOKEN", "PR_NUMBER", 
        "PR_TITLE", "PR_BASE_SHA", "PR_HEAD_SHA", "REPO_NAME"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        sys.exit(1)
    
    # Get PR information
    pr_info = {
        "number": os.getenv("PR_NUMBER"),
        "title": os.getenv("PR_TITLE"),
        "body": os.getenv("PR_BODY", ""),
        "repo_name": os.getenv("REPO_NAME"),
        "base_sha": os.getenv("PR_BASE_SHA"),
        "head_sha": os.getenv("PR_HEAD_SHA"),
    }
    
    logger.info(f"Reviewing PR #{pr_info['number']}: {pr_info['title']}")
    
    try:
        # Get the PR diff
        diff_content = get_pr_diff()
        
        # Create the review prompt
        prompt = create_review_prompt(pr_info, diff_content)
        
        # Configure LLM
        api_key = os.getenv("LLM_API_KEY")
        model = os.getenv("LLM_MODEL", "openhands/claude-sonnet-4-5-20250929")
        base_url = os.getenv("LLM_BASE_URL")
        
        llm_config = {
            "model": model,
            "api_key": SecretStr(api_key),
            "service_id": "pr_review_agent",
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
        
        # Create conversation
        conversation = Conversation(
            agent=agent,
            workspace=cwd,
        )
        
        logger.info("Starting PR review analysis...")
        logger.info(f"Analyzing {len(diff_content)} characters of diff content")
        
        # Send the prompt and run the agent
        conversation.send_message(prompt)
        conversation.run()
        
        # Get the agent's response
        messages = conversation.get_messages()
        if not messages:
            raise RuntimeError("No response from the review agent")
            
        # Find the last assistant message
        review_content = None
        for message in reversed(messages):
            if message.role == "assistant" and message.content:
                review_content = message.content
                break
                
        if not review_content:
            raise RuntimeError("No review content generated by the agent")
            
        logger.info(f"Generated review with {len(review_content)} characters")
        
        # Post the review comment
        post_review_comment(review_content)
        
        logger.info("PR review completed successfully")
        
    except Exception as e:
        logger.error(f"PR review failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()