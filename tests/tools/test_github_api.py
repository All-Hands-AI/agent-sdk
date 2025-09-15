"""Tests for GitHubTool."""

import tempfile
from unittest.mock import Mock, patch

import pytest

from openhands.tools.github_api.definition import (
    GitHubCloneRepoAction,
    GitHubExecutor,
    GitHubTool,
)


def test_github_executor_init():
    """Test GitHubExecutor initialization."""
    executor = GitHubExecutor(github_token="test_token")
    assert executor.github_token == "test_token"


@patch.dict("os.environ", {}, clear=True)
def test_github_executor_init_missing_token():
    """Test GitHubExecutor initialization with missing token."""
    with pytest.raises(ValueError, match="GitHub token is required"):
        GitHubExecutor(github_token=None)


@patch("subprocess.run")
def test_executor_call_success(mock_run):
    """Test successful repository cloning via executor call."""
    mock_run.return_value = Mock(
        returncode=0, stdout="Cloning into 'test-repo'...", stderr=""
    )

    executor = GitHubExecutor(github_token="test_token")
    action = GitHubCloneRepoAction(repo="owner/test-repo")

    with tempfile.TemporaryDirectory() as temp_dir:
        executor.working_dir = temp_dir
        result = executor(action)

        # Verify git clone was called
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "git" in call_args
        assert "clone" in call_args
        assert "https://test_token@github.com/owner/test-repo.git" in call_args

        # Verify result
        assert result.success is True
        assert result.error is None
        assert result.repo == "owner/test-repo"
        assert result.target_path is not None
        assert "test-repo" in result.target_path


@patch("subprocess.run")
def test_executor_call_git_error(mock_run):
    """Test git command failure."""
    mock_run.return_value = Mock(returncode=1, stdout="", stderr="Permission denied")

    executor = GitHubExecutor(github_token="test_token")
    action = GitHubCloneRepoAction(repo="owner/test-repo")

    with tempfile.TemporaryDirectory() as temp_dir:
        executor.working_dir = temp_dir
        result = executor(action)

        assert result.success is False
        assert result.error is not None
        assert "Permission denied" in result.error


@patch("subprocess.run")
def test_executor_call_timeout(mock_run):
    """Test git command timeout."""
    import subprocess

    mock_run.side_effect = subprocess.TimeoutExpired("git", 300)

    executor = GitHubExecutor(github_token="test_token")
    action = GitHubCloneRepoAction(repo="owner/test-repo")

    with tempfile.TemporaryDirectory() as temp_dir:
        executor.working_dir = temp_dir
        result = executor(action)

        assert result.success is False
        assert result.error is not None
        assert "timed out" in result.error


def test_github_tool_create():
    """Test GitHubTool.create() method."""
    tool = GitHubTool.create(github_token="test_token")
    assert isinstance(tool.executor, GitHubExecutor)
    assert tool.executor.github_token == "test_token"


@patch("subprocess.run")
def test_github_tool_execution(mock_run):
    """Test GitHubTool execution."""
    mock_run.return_value = Mock(
        returncode=0, stdout="Cloning into 'test-repo'...", stderr=""
    )

    tool = GitHubTool.create(github_token="test_token")
    action = GitHubCloneRepoAction(repo="owner/test-repo")

    with tempfile.TemporaryDirectory() as temp_dir:
        assert isinstance(tool.executor, GitHubExecutor)
        tool.executor.working_dir = temp_dir
        result = tool.executor(action)

        # Verify the result
        assert result.success is True
        assert result.error is None
        assert result.repo == "owner/test-repo"


@patch("subprocess.run")
def test_executor_with_branch(mock_run):
    """Test executor with specific branch."""
    mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

    executor = GitHubExecutor(github_token="test_token")
    action = GitHubCloneRepoAction(repo="owner/test-repo", branch="develop")

    with tempfile.TemporaryDirectory() as temp_dir:
        executor.working_dir = temp_dir
        executor(action)

        # Verify git clone was called with branch
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "--branch" in call_args
        assert "develop" in call_args


@patch("subprocess.run")
def test_executor_with_depth(mock_run):
    """Test executor with shallow clone depth."""
    mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

    executor = GitHubExecutor(github_token="test_token")
    action = GitHubCloneRepoAction(repo="owner/test-repo", depth=1)

    with tempfile.TemporaryDirectory() as temp_dir:
        executor.working_dir = temp_dir
        executor(action)

        # Verify git clone was called with depth
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "--depth" in call_args
        assert "1" in call_args


def test_github_clone_repo_action():
    """Test GitHubCloneRepoAction creation and validation."""
    action = GitHubCloneRepoAction(repo="owner/test-repo")
    assert action.repo == "owner/test-repo"
    assert action.branch is None
    assert action.depth is None

    # Test with all parameters
    action = GitHubCloneRepoAction(
        repo="owner/test-repo", branch="main", depth=5, target_dir="./custom"
    )
    assert action.repo == "owner/test-repo"
    assert action.branch == "main"
    assert action.depth == 5
    assert action.target_dir == "./custom"

    # Test validation
    with pytest.raises(ValueError):
        GitHubCloneRepoAction(repo="owner/test-repo", depth=0)  # depth too low


@patch("subprocess.run")
def test_token_masking(mock_run):
    """Test that GitHub token is masked in output."""
    mock_run.return_value = Mock(
        returncode=0,
        stdout="Cloning into 'test-repo'...\nhttps://test_token@github.com/owner/test-repo.git",
        stderr="",
    )

    executor = GitHubExecutor(github_token="test_token")
    action = GitHubCloneRepoAction(repo="owner/test-repo")

    with tempfile.TemporaryDirectory() as temp_dir:
        executor.working_dir = temp_dir
        result = executor(action)

        # Verify token is masked in output
        assert "test_token" not in result.output
        assert "***" in result.output
