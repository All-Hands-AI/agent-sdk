"""Shared test utilities for execute_bash tests."""

import tempfile

from openhands.core.logger import get_logger
from openhands.tools.execute_bash.bash_session import BashSession
from openhands.tools.execute_bash.constants import TIMEOUT_MESSAGE_TEMPLATE


logger = get_logger(__name__)


def get_no_change_timeout_suffix(timeout_seconds):
    """Helper function to generate the expected no-change timeout suffix."""
    return (
        f"\n[The command has no new output after {timeout_seconds} seconds. "
        f"{TIMEOUT_MESSAGE_TEMPLATE}]"
    )


def create_test_bash_session(work_dir=None):
    """Create a BashSession for testing purposes."""
    if work_dir is None:
        work_dir = tempfile.mkdtemp()
    return BashSession(work_dir=work_dir)


def cleanup_bash_session(session):
    """Clean up a BashSession after testing."""
    if hasattr(session, "close"):
        session.close()
