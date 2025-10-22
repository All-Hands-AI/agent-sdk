"""Tests for git_router.py endpoints."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from openhands.agent_server.api import create_app
from openhands.agent_server.config import Config
from openhands.agent_server.models import ConversationInfo
from openhands.sdk.git.models import GitChange, GitChangeStatus, GitDiff
from openhands.sdk.workspace import LocalWorkspace


@pytest.fixture
def client():
    """Create a test client for the FastAPI app without authentication."""
    config = Config(session_api_keys=[])  # Disable authentication
    return TestClient(create_app(config), raise_server_exceptions=False)


@pytest.fixture
def mock_conversation_info():
    """Create a mock conversation info for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a mock workspace with the working_dir attribute
        workspace = LocalWorkspace(working_dir=temp_dir)

        # Create a mock ConversationInfo with required fields
        conversation_info = MagicMock(spec=ConversationInfo)
        conversation_info.conversation_id = uuid4()
        conversation_info.workspace = workspace

        yield conversation_info


@pytest.mark.asyncio
async def test_git_changes_success(client, mock_conversation_info):
    """Test successful git changes endpoint."""
    # Mock the conversation service
    with patch(
        "openhands.agent_server.git_router.conversation_service"
    ) as mock_conv_service:
        mock_conv_service.get_conversation = AsyncMock(
            return_value=mock_conversation_info
        )

        # Mock the get_git_changes function
        expected_changes = [
            GitChange(status=GitChangeStatus.ADDED, path=Path("new_file.py")),
            GitChange(status=GitChangeStatus.UPDATED, path=Path("existing_file.py")),
            GitChange(status=GitChangeStatus.DELETED, path=Path("old_file.py")),
        ]

        with patch(
            "openhands.agent_server.git_router.get_git_changes"
        ) as mock_get_changes:
            mock_get_changes.return_value = expected_changes

            response = client.get(
                f"/api/git/changes/{mock_conversation_info.conversation_id}"
            )

            assert response.status_code == 200
            response_data = response.json()

            # Verify the response structure
            assert len(response_data) == 3
            assert response_data[0]["status"] == "ADDED"
            assert response_data[0]["path"] == "new_file.py"
            assert response_data[1]["status"] == "UPDATED"
            assert response_data[1]["path"] == "existing_file.py"
            assert response_data[2]["status"] == "DELETED"
            assert response_data[2]["path"] == "old_file.py"

            # Verify the mocks were called correctly
            mock_conv_service.get_conversation.assert_called_once_with(
                mock_conversation_info.conversation_id
            )
            mock_get_changes.assert_called_once_with(
                mock_conversation_info.workspace.working_dir
            )


@pytest.mark.asyncio
async def test_git_changes_empty_result(client, mock_conversation_info):
    """Test git changes endpoint with no changes."""
    with patch(
        "openhands.agent_server.git_router.conversation_service"
    ) as mock_conv_service:
        mock_conv_service.get_conversation = AsyncMock(
            return_value=mock_conversation_info
        )

        with patch(
            "openhands.agent_server.git_router.get_git_changes"
        ) as mock_get_changes:
            mock_get_changes.return_value = []

            response = client.get(
                f"/api/git/changes/{mock_conversation_info.conversation_id}"
            )

            assert response.status_code == 200
            assert response.json() == []


@pytest.mark.asyncio
async def test_git_changes_conversation_not_found(client):
    """Test git changes endpoint when conversation is not found."""
    conversation_id = uuid4()

    with patch(
        "openhands.agent_server.git_router.conversation_service"
    ) as mock_conv_service:
        mock_conv_service.get_conversation = AsyncMock(return_value=None)

        response = client.get(f"/api/git/changes/{conversation_id}")

        # Should return 500 due to assertion error when conversation not found
        assert response.status_code == 500
        mock_conv_service.get_conversation.assert_called_once_with(conversation_id)


@pytest.mark.asyncio
async def test_git_diff_success(client, mock_conversation_info):
    """Test successful git diff endpoint."""
    with patch(
        "openhands.agent_server.git_router.conversation_service"
    ) as mock_conv_service:
        mock_conv_service.get_conversation = AsyncMock(
            return_value=mock_conversation_info
        )

        # Mock the get_git_diff function
        expected_diff = GitDiff(
            modified="def new_function():\n    return 'updated'",
            original="def old_function():\n    return 'original'",
        )

        with patch("openhands.agent_server.git_router.get_git_diff") as mock_get_diff:
            mock_get_diff.return_value = expected_diff

            test_path = "src/test_file.py"
            response = client.get(
                f"/api/git/diff/{mock_conversation_info.conversation_id}/{test_path}"
            )

            assert response.status_code == 200
            response_data = response.json()

            # Verify the response structure
            assert response_data["modified"] == expected_diff.modified
            assert response_data["original"] == expected_diff.original

            # Verify the mocks were called correctly
            mock_conv_service.get_conversation.assert_called_once_with(
                mock_conversation_info.conversation_id
            )
            expected_file_path = str(
                Path(mock_conversation_info.workspace.working_dir) / test_path
            )
            mock_get_diff.assert_called_once_with(expected_file_path)


@pytest.mark.asyncio
async def test_git_diff_with_none_values(client, mock_conversation_info):
    """Test git diff endpoint with None values."""
    with patch(
        "openhands.agent_server.git_router.conversation_service"
    ) as mock_conv_service:
        mock_conv_service.get_conversation = AsyncMock(
            return_value=mock_conversation_info
        )

        # Mock the get_git_diff function with None values
        expected_diff = GitDiff(modified=None, original=None)

        with patch("openhands.agent_server.git_router.get_git_diff") as mock_get_diff:
            mock_get_diff.return_value = expected_diff

            test_path = "nonexistent_file.py"
            response = client.get(
                f"/api/git/diff/{mock_conversation_info.conversation_id}/{test_path}"
            )

            assert response.status_code == 200
            response_data = response.json()

            # Verify the response structure
            assert response_data["modified"] is None
            assert response_data["original"] is None


@pytest.mark.asyncio
async def test_git_diff_conversation_not_found(client):
    """Test git diff endpoint when conversation is not found."""
    conversation_id = uuid4()

    with patch(
        "openhands.agent_server.git_router.conversation_service"
    ) as mock_conv_service:
        mock_conv_service.get_conversation = AsyncMock(return_value=None)

        response = client.get(f"/api/git/diff/{conversation_id}/test_file.py")

        # Should return 500 due to assertion error when conversation not found
        assert response.status_code == 500
        mock_conv_service.get_conversation.assert_called_once_with(conversation_id)


@pytest.mark.asyncio
async def test_git_diff_nested_path(client, mock_conversation_info):
    """Test git diff endpoint with nested file path."""
    with patch(
        "openhands.agent_server.git_router.conversation_service"
    ) as mock_conv_service:
        mock_conv_service.get_conversation = AsyncMock(
            return_value=mock_conversation_info
        )

        expected_diff = GitDiff(modified="updated content", original="original content")

        with patch("openhands.agent_server.git_router.get_git_diff") as mock_get_diff:
            mock_get_diff.return_value = expected_diff

            # Test with nested path
            test_path = "src/utils/helper.py"
            response = client.get(
                f"/api/git/diff/{mock_conversation_info.conversation_id}/{test_path}"
            )

            assert response.status_code == 200

            # Verify the correct path was constructed
            expected_file_path = str(
                Path(mock_conversation_info.workspace.working_dir) / test_path
            )
            mock_get_diff.assert_called_once_with(expected_file_path)


@pytest.mark.asyncio
async def test_git_changes_with_all_status_types(client, mock_conversation_info):
    """Test git changes endpoint with all possible GitChangeStatus values."""
    with patch(
        "openhands.agent_server.git_router.conversation_service"
    ) as mock_conv_service:
        mock_conv_service.get_conversation = AsyncMock(
            return_value=mock_conversation_info
        )

        # Test all possible status types
        expected_changes = [
            GitChange(status=GitChangeStatus.ADDED, path=Path("added.py")),
            GitChange(status=GitChangeStatus.UPDATED, path=Path("updated.py")),
            GitChange(status=GitChangeStatus.DELETED, path=Path("deleted.py")),
            GitChange(status=GitChangeStatus.MOVED, path=Path("moved.py")),
        ]

        with patch(
            "openhands.agent_server.git_router.get_git_changes"
        ) as mock_get_changes:
            mock_get_changes.return_value = expected_changes

            response = client.get(
                f"/api/git/changes/{mock_conversation_info.conversation_id}"
            )

            assert response.status_code == 200
            response_data = response.json()

            assert len(response_data) == 4
            assert response_data[0]["status"] == "ADDED"
            assert response_data[1]["status"] == "UPDATED"
            assert response_data[2]["status"] == "DELETED"
            assert response_data[3]["status"] == "MOVED"


@pytest.mark.asyncio
async def test_git_changes_with_complex_paths(client, mock_conversation_info):
    """Test git changes endpoint with complex file paths."""
    with patch(
        "openhands.agent_server.git_router.conversation_service"
    ) as mock_conv_service:
        mock_conv_service.get_conversation = AsyncMock(
            return_value=mock_conversation_info
        )

        # Test with various path complexities
        expected_changes = [
            GitChange(
                status=GitChangeStatus.ADDED,
                path=Path("src/deep/nested/file.py"),
            ),
            GitChange(
                status=GitChangeStatus.UPDATED,
                path=Path("file with spaces.txt"),
            ),
            GitChange(
                status=GitChangeStatus.DELETED,
                path=Path("special-chars_file@123.py"),
            ),
        ]

        with patch(
            "openhands.agent_server.git_router.get_git_changes"
        ) as mock_get_changes:
            mock_get_changes.return_value = expected_changes

            response = client.get(
                f"/api/git/changes/{mock_conversation_info.conversation_id}"
            )

            assert response.status_code == 200
            response_data = response.json()

            assert len(response_data) == 3
            assert response_data[0]["path"] == "src/deep/nested/file.py"
            assert response_data[1]["path"] == "file with spaces.txt"
            assert response_data[2]["path"] == "special-chars_file@123.py"
