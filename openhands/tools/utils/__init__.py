"""Shared utilities."""

import os
import shutil
import subprocess

from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


def _check_ripgrep_available() -> bool:
    """Check if ripgrep (rg) is available on the system.

    Can be overridden by setting OPENHANDS_DISABLE_RIPGREP=true to force fallback.

    Returns:
        True if ripgrep is available, False otherwise
    """
    # Check if ripgrep is explicitly disabled via environment variable
    if os.getenv("OPENHANDS_DISABLE_RIPGREP", "").lower() in {"true", "1", "yes"}:
        logger.info(
            "Ripgrep disabled via OPENHANDS_DISABLE_RIPGREP environment variable"
        )
        return False

    try:
        # First check if rg is in PATH
        if shutil.which("rg") is None:
            return False

        # Try to run rg --version to ensure it's working
        result = subprocess.run(
            ["rg", "--version"], capture_output=True, text=True, timeout=5, check=False
        )
        return result.returncode == 0
    except Exception:
        return False


def _log_ripgrep_fallback_warning(tool_name: str, fallback_method: str) -> None:
    """Log a warning about falling back from ripgrep to alternative method.

    Args:
        tool_name: Name of the tool (e.g., "glob", "grep")
        fallback_method: Description of the fallback method being used
    """
    # Check if this is due to explicit disabling
    if os.getenv("OPENHANDS_DISABLE_RIPGREP", "").lower() in {"true", "1", "yes"}:
        logger.info(
            f"{tool_name}: using {fallback_method} "
            f"(ripgrep disabled via OPENHANDS_DISABLE_RIPGREP)"
        )
    else:
        logger.warning(
            f"{tool_name}: ripgrep (rg) not available. "
            f"Falling back to {fallback_method}. "
            f"For better performance, consider installing ripgrep: "
            f"https://github.com/BurntSushi/ripgrep#installation"
        )
