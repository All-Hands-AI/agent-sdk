"""
Automated TODO Management Example

Scans for TODO(openhands) comments and creates pull requests to implement them.

Usage:
    python 20_automated_todo_management_concise.py --repo-path /path/to/repo

Environment Variables:
    GITHUB_TOKEN: Required for creating pull requests
    OPENAI_API_KEY: Required for LLM operations
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import requests
from pydantic import SecretStr

from openhands.sdk import LLM, Agent, Conversation, get_logger
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool


logger = get_logger(__name__)


@dataclass
class TodoItem:
    file_path: str
    line_number: int
    todo_text: str
    context: str
    unique_id: str = field(default="")

    def __post_init__(self):
        if not self.unique_id:
            content = f"{self.file_path}:{self.line_number}:{self.todo_text}"
            self.unique_id = hashlib.md5(content.encode()).hexdigest()[:8]


class TodoManager:
    """Main class that handles TODO scanning, implementation, and PR creation."""

    def __init__(
        self,
        repo_path: str,
        repo_owner: str,
        repo_name: str,
        github_token: str,
        llm: LLM,
        config: dict | None = None,
    ):
        self.repo_path = Path(repo_path)
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.github_token = github_token
        self.llm = llm
        self.config = config or self._load_default_config()

        # GitHub API setup
        self.github_headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.base_url = "https://api.github.com"

        # Regex patterns
        self.todo_pattern = re.compile(r"#\s*TODO\(openhands\):\s*(.+)", re.IGNORECASE)
        self.in_progress_pattern = re.compile(
            r"#\s*TODO\(openhands-in-progress\):\s*(.+)", re.IGNORECASE
        )

    def _load_default_config(self) -> dict:
        """Load default configuration."""
        config_path = self.repo_path.parent / "configs" / "todo_config.json"
        if config_path.exists():
            with open(config_path) as f:
                return json.load(f)

        return {
            "max_todos_per_run": 3,
            "context_lines": 5,
            "excluded_dirs": [".venv", "__pycache__", ".git", "node_modules"],
            "file_extensions": ["*.py"],
            "pr_template": {
                "title": "Implement TODO: {todo_text}",
                "body": (
                    "This PR implements the TODO comment:\n\n> {todo_text}\n\n"
                    "Found in `{file_path}` at line {line_number}.\n\n"
                    "## Implementation\n\n{implementation_description}\n\n---\n"
                    "*This PR was created automatically by the OpenHands TODO "
                    "automation system.*"
                ),
            },
        }

    def scan_todos(self) -> list[TodoItem]:
        """Scan repository for TODO(openhands) comments."""
        todos = []

        for ext in self.config["file_extensions"]:
            for file_path in self.repo_path.rglob(ext):
                # Skip excluded directories
                if any(
                    part in file_path.parts for part in self.config["excluded_dirs"]
                ):
                    continue

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()

                    for line_num, line in enumerate(lines, 1):
                        if self.in_progress_pattern.search(line):
                            continue

                        match = self.todo_pattern.search(line)
                        if match:
                            todo_text = match.group(1).strip()
                            context = self._extract_context(lines, line_num)

                            todo = TodoItem(
                                file_path=str(file_path.relative_to(self.repo_path)),
                                line_number=line_num,
                                todo_text=todo_text,
                                context=context,
                            )
                            todos.append(todo)

                except Exception as e:
                    logger.warning(f"Error reading {file_path}: {e}")

        return todos

    def _extract_context(self, lines: list[str], line_num: int) -> str:
        """Extract context around a TODO comment."""
        context_lines = self.config["context_lines"]
        start = max(0, line_num - context_lines - 1)
        end = min(len(lines), line_num + context_lines)
        return "".join(lines[start:end])

    def implement_todo(self, todo: TodoItem) -> tuple[str, str]:
        """Use OpenHands to implement a TODO."""
        # Mark TODO as in progress
        self._mark_todo_in_progress(todo)

        try:
            # Create agent with tools
            tools = [
                BashTool.create(working_dir=str(self.repo_path)),
                FileEditorTool.create(),
            ]

            agent = Agent(llm=self.llm, tools=tools)
            conversation = Conversation(agent=agent)

            # Create implementation prompt
            prompt = f"""I need to implement this TODO comment:

TODO: {todo.todo_text}

File: {todo.file_path}
Line: {todo.line_number}

Context:
```
{todo.context}
```

Please analyze the TODO and implement the requested functionality.
Make the necessary changes to the codebase.
Provide a brief description of what you implemented.
"""

            # Get implementation from agent
            conversation.send_message(prompt)
            conversation.run()

            # Get the final response from the conversation
            description = self._get_final_response(conversation)

            return "success", description

        except Exception as e:
            logger.error(f"Error implementing TODO {todo.unique_id}: {e}")
            self._unmark_todo_in_progress(todo)
            return "error", str(e)

    def _get_final_response(self, conversation) -> str:
        """Extract the final response from the conversation."""
        from openhands.sdk.event import MessageEvent
        from openhands.sdk.llm import TextContent

        events = list(conversation.state.events)

        # Look for the last message event from the agent
        for event in reversed(events):
            if isinstance(event, MessageEvent) and event.source == "agent":
                # Extract text content from the message
                content_parts = []
                for content_item in event.llm_message.content:
                    if isinstance(content_item, TextContent):
                        content_parts.append(content_item.text)
                if content_parts:
                    return " ".join(content_parts)

        return "Implementation completed successfully."

    def _extract_implementation_description(self, response: str) -> str:
        """Extract a concise implementation description from agent response."""
        # Simple extraction - take first few sentences
        sentences = response.split(". ")
        return ". ".join(sentences[:3]) + "." if len(sentences) > 3 else response

    def _mark_todo_in_progress(self, todo: TodoItem):
        """Mark a TODO as in progress to prevent duplicate processing."""
        file_path = self.repo_path / todo.file_path
        with open(file_path, "r") as f:
            content = f.read()

        # Replace TODO(openhands) with TODO(openhands-in-progress)
        updated_content = content.replace(
            f"TODO(openhands): {todo.todo_text}",
            f"TODO(openhands-in-progress): {todo.todo_text}",
        )

        with open(file_path, "w") as f:
            f.write(updated_content)

    def _unmark_todo_in_progress(self, todo: TodoItem):
        """Unmark a TODO if implementation failed."""
        file_path = self.repo_path / todo.file_path
        with open(file_path, "r") as f:
            content = f.read()

        updated_content = content.replace(
            f"TODO(openhands-in-progress): {todo.todo_text}",
            f"TODO(openhands): {todo.todo_text}",
        )

        with open(file_path, "w") as f:
            f.write(updated_content)

    def create_pull_request(
        self, todo: TodoItem, implementation_description: str
    ) -> dict:
        """Create a pull request for the implemented TODO."""
        branch_name = f"todo-{todo.unique_id}"

        # Create branch
        main_sha = self._get_main_branch_sha()
        self._create_branch(branch_name, main_sha)

        # Commit changes
        self._commit_changes(branch_name, todo, implementation_description)

        # Create PR
        pr_data = {
            "title": self.config["pr_template"]["title"].format(
                todo_text=todo.todo_text
            ),
            "body": self.config["pr_template"]["body"].format(
                todo_text=todo.todo_text,
                file_path=todo.file_path,
                line_number=todo.line_number,
                implementation_description=implementation_description,
            ),
            "head": branch_name,
            "base": "main",
        }

        response = requests.post(
            f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls",
            headers=self.github_headers,
            json=pr_data,
        )

        if response.status_code == 201:
            return response.json()
        else:
            raise Exception(f"Failed to create PR: {response.text}")

    def _get_main_branch_sha(self) -> str:
        """Get the SHA of the main branch."""
        response = requests.get(
            f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/refs/heads/main",
            headers=self.github_headers,
        )
        return response.json()["object"]["sha"]

    def _create_branch(self, branch_name: str, base_sha: str):
        """Create a new branch."""
        requests.post(
            f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/refs",
            headers=self.github_headers,
            json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
        )

    def _commit_changes(self, branch_name: str, todo: TodoItem, description: str):
        """Commit all changes to the branch."""
        # Get current tree
        response = requests.get(
            f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/refs/heads/{branch_name}",
            headers=self.github_headers,
        )
        # Get current commit SHA for reference
        response.json()["object"]["sha"]

        # Create commit with all changes
        subprocess.run(["git", "add", "."], cwd=self.repo_path, check=True)
        subprocess.run(
            [
                "git",
                "commit",
                "-m",
                f"Implement TODO: {todo.todo_text}\n\n{description}",
            ],
            cwd=self.repo_path,
            check=True,
        )

        # Push to GitHub
        subprocess.run(
            ["git", "push", "origin", branch_name], cwd=self.repo_path, check=True
        )

    def run(self, dry_run: bool = False) -> dict:
        """Main execution method."""
        logger.info("Starting automated TODO management...")

        # Scan for TODOs
        todos = self.scan_todos()
        logger.info(f"Found {len(todos)} TODO(openhands) comments")

        if not todos:
            return {"status": "success", "message": "No TODOs found", "processed": 0}

        if dry_run:
            logger.info("DRY RUN: Would process the following TODOs:")
            for todo in todos[: self.config["max_todos_per_run"]]:
                logger.info(
                    f"  - {todo.file_path}:{todo.line_number} - {todo.todo_text}"
                )
            return {"status": "success", "message": "Dry run completed", "processed": 0}

        # Process TODOs
        results = []
        processed = 0

        for todo in todos[: self.config["max_todos_per_run"]]:
            logger.info(f"Processing TODO: {todo.todo_text}")

            # Implement TODO
            status, description = self.implement_todo(todo)

            if status == "success":
                try:
                    # Create PR
                    pr = self.create_pull_request(todo, description)
                    results.append(
                        {
                            "todo_id": todo.unique_id,
                            "status": "success",
                            "pr_url": pr["html_url"],
                        }
                    )
                    processed += 1
                    logger.info(f"Created PR: {pr['html_url']}")
                except Exception as e:
                    logger.error(f"Failed to create PR for TODO {todo.unique_id}: {e}")
                    results.append(
                        {
                            "todo_id": todo.unique_id,
                            "status": "pr_failed",
                            "error": str(e),
                        }
                    )
            else:
                results.append(
                    {
                        "todo_id": todo.unique_id,
                        "status": "implementation_failed",
                        "error": description,
                    }
                )

        return {
            "status": "success",
            "message": f"Processed {processed} TODOs",
            "processed": processed,
            "results": results,
        }


def main():
    parser = argparse.ArgumentParser(description="Automated TODO Management")
    parser.add_argument("--repo-path", required=True, help="Path to repository")
    parser.add_argument("--repo-owner", required=True, help="GitHub repository owner")
    parser.add_argument("--repo-name", required=True, help="GitHub repository name")
    parser.add_argument(
        "--dry-run", action="store_true", help="Run without making changes"
    )
    parser.add_argument("--config", help="Path to configuration file")

    args = parser.parse_args()

    # Load configuration
    config: dict | None = None
    if args.config:
        with open(args.config) as f:
            config = json.load(f)

    # Initialize LLM
    llm = LLM(
        model=os.getenv("LLM_MODEL", "gpt-4"),
        api_key=SecretStr(os.getenv("OPENAI_API_KEY", "")),
        base_url=os.getenv("LLM_BASE_URL"),
    )

    # Initialize manager
    manager = TodoManager(
        repo_path=args.repo_path,
        repo_owner=args.repo_owner,
        repo_name=args.repo_name,
        github_token=os.getenv("GITHUB_TOKEN", ""),
        llm=llm,
        config=config,
    )

    # Run automation
    result = manager.run(dry_run=args.dry_run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
