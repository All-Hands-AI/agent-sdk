"""GitHub API tool implementation."""

import os
import subprocess
from collections.abc import Sequence
from pathlib import Path

from pydantic import Field
from rich.text import Text

from openhands.sdk.llm import ImageContent, TextContent
from openhands.sdk.tool import (
    ActionBase,
    ObservationBase,
    Tool,
    ToolAnnotations,
    ToolExecutor,
)


class GitHubCloneRepoAction(ActionBase):
    """Schema for GitHub repository cloning."""

    repo: str = Field(
        description=(
            "Repository to clone in format 'owner/repo' "
            "(e.g., 'All-Hands-AI/OpenHands'). Can also be a full GitHub URL."
        )
    )
    target_dir: str | None = Field(
        default=None,
        description=(
            "Target directory to clone into. If not provided, uses the repo name. "
            "Path can be relative or absolute."
        ),
    )
    branch: str | None = Field(
        default=None,
        description=(
            "Specific branch to clone. If not provided, clones the default branch."
        ),
    )
    depth: int | None = Field(
        default=None,
        description=(
            "Create a shallow clone with history truncated to the specified "
            "number of commits."
        ),
        ge=1,
    )

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation."""
        content = Text()
        content.append("📥 GitHub Clone: ", style="bold blue")
        content.append(self.repo, style="white")

        if self.branch:
            content.append(f" (branch: {self.branch})", style="dim cyan")
        if self.target_dir:
            content.append(f" → {self.target_dir}", style="dim yellow")
        if self.depth:
            content.append(f" (depth: {self.depth})", style="dim green")

        return content


class GitHubCloneRepoObservation(ObservationBase):
    """Observation from GitHub repository cloning."""

    repo: str = Field(description="The repository that was cloned.")
    target_path: str | None = Field(
        default=None, description="The actual path where the repo was cloned."
    )
    success: bool = Field(
        default=False, description="Whether the clone was successful."
    )
    error: str | None = Field(default=None, description="Error message if any.")
    output: str = Field(default="", description="Command output from git clone.")

    @property
    def agent_observation(self) -> Sequence[TextContent | ImageContent]:
        if not self.success:
            return [TextContent(text=f"❌ Failed to clone {self.repo}: {self.error}")]

        result_lines = [
            f"✅ Successfully cloned {self.repo}",
            f"📁 Location: {self.target_path}",
        ]

        if self.output.strip():
            result_lines.extend(["", "Git output:", self.output])

        return [TextContent(text="\n".join(result_lines))]

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation."""
        content = Text()

        if not self.success:
            content.append("❌ ", style="red bold")
            content.append(f"Failed to clone {self.repo}", style="red")
            if self.error:
                content.append(f"\nError: {self.error}", style="red")
            return content

        content.append("✅ ", style="green bold")
        content.append(f"Successfully cloned {self.repo}", style="green")
        if self.target_path:
            content.append(f"\n📁 Location: {self.target_path}", style="blue")

        return content


class GitHubExecutor(ToolExecutor[GitHubCloneRepoAction, GitHubCloneRepoObservation]):
    """Executor for GitHub operations."""

    def __init__(self, github_token: str | None = None, working_dir: str | None = None):
        """Initialize GitHub executor.

        Args:
            github_token: GitHub token for authentication. If None, reads from
                GITHUB_TOKEN env var.
            working_dir: Working directory for git operations. Defaults to
                current directory.
        """
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        self.working_dir = working_dir or os.getcwd()

        if not self.github_token:
            raise ValueError(
                "GitHub token is required. Set GITHUB_TOKEN environment variable "
                "or pass github_token parameter."
            )

    def __call__(self, action: GitHubCloneRepoAction) -> GitHubCloneRepoObservation:
        """Execute GitHub repository cloning."""
        try:
            # Parse repository name
            repo = action.repo
            if repo.startswith("https://github.com/"):
                repo = repo.replace("https://github.com/", "").rstrip(".git")
            elif "/" not in repo:
                return GitHubCloneRepoObservation(
                    repo=action.repo,
                    error="Repository must be in format 'owner/repo' or a GitHub URL",
                )

            # Determine target directory
            if action.target_dir:
                target_path = Path(self.working_dir) / action.target_dir
            else:
                repo_name = repo.split("/")[-1]
                target_path = Path(self.working_dir) / repo_name

            # Check if directory already exists
            if target_path.exists():
                return GitHubCloneRepoObservation(
                    repo=action.repo,
                    target_path=str(target_path),
                    error=f"Directory {target_path} already exists",
                )

            # Build git clone command
            clone_url = f"https://{self.github_token}@github.com/{repo}.git"
            cmd = ["git", "clone"]

            if action.branch:
                cmd.extend(["--branch", action.branch])

            if action.depth:
                cmd.extend(["--depth", str(action.depth)])

            cmd.extend([clone_url, str(target_path)])

            # Execute git clone
            result = subprocess.run(
                cmd,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown git error"
                # Mask the token in error messages
                if self.github_token:
                    error_msg = error_msg.replace(self.github_token, "***")
                return GitHubCloneRepoObservation(
                    repo=action.repo,
                    error=error_msg,
                    output=result.stdout,
                )

            # Mask token in output
            output = result.stdout
            if self.github_token:
                output = output.replace(self.github_token, "***")

            return GitHubCloneRepoObservation(
                repo=action.repo,
                target_path=str(target_path),
                success=True,
                output=output,
            )

        except subprocess.TimeoutExpired:
            return GitHubCloneRepoObservation(
                repo=action.repo,
                error="Git clone operation timed out after 5 minutes",
            )
        except Exception as e:
            return GitHubCloneRepoObservation(
                repo=action.repo,
                error=f"Unexpected error: {str(e)}",
            )


TOOL_DESCRIPTION = """Clone GitHub repositories using git with authentication.

This tool allows you to clone GitHub repositories to your local filesystem using
a GitHub token for authentication.

### Authentication
Requires GITHUB_TOKEN environment variable to be set with a valid GitHub personal
access token or fine-grained token.

### Repository Format
- Use 'owner/repo' format (e.g., 'All-Hands-AI/OpenHands')
- Or provide full GitHub URL (e.g., 'https://github.com/All-Hands-AI/OpenHands')

### Features
- Clone specific branches
- Shallow clones with depth limit
- Custom target directories
- Automatic token masking in outputs
- Timeout protection (5 minutes)

### Examples
- Clone a repository: `All-Hands-AI/OpenHands`
- Clone specific branch: `All-Hands-AI/OpenHands` with branch `main`
- Shallow clone: `All-Hands-AI/OpenHands` with depth `1`
- Custom directory: `All-Hands-AI/OpenHands` to `./my-openhands`

### Output
Returns the local path where the repository was cloned and any git output messages.
"""


github_clone_repo_tool = Tool(
    name="github_clone_repo",
    action_type=GitHubCloneRepoAction,
    observation_type=GitHubCloneRepoObservation,
    description=TOOL_DESCRIPTION,
    annotations=ToolAnnotations(
        title="github_clone_repo",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)


class GitHubTool(Tool[GitHubCloneRepoAction, GitHubCloneRepoObservation]):
    """A Tool subclass for GitHub operations."""

    @classmethod
    def create(
        cls,
        github_token: str | None = None,
        working_dir: str | None = None,
    ) -> "GitHubTool":
        """Initialize GitHubTool with credentials and working directory.

        Args:
            github_token: GitHub token for authentication. If None, reads from
                GITHUB_TOKEN env var.
            working_dir: Working directory for git operations. Defaults to
                current directory.
        """
        executor = GitHubExecutor(github_token=github_token, working_dir=working_dir)

        return cls(
            name=github_clone_repo_tool.name,
            description=TOOL_DESCRIPTION,
            action_type=GitHubCloneRepoAction,
            observation_type=GitHubCloneRepoObservation,
            annotations=github_clone_repo_tool.annotations,
            executor=executor,
        )
