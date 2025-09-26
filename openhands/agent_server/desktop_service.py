"""Desktop service for launching VNC desktop via desktop_launch.sh script."""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Optional

from openhands.sdk.logger import get_logger

logger = get_logger(__name__)


class DesktopService:
    """Simple desktop service that launches desktop_launch.sh script."""

    def __init__(self):
        self._proc: Optional[asyncio.subprocess.Process] = None
        self.novnc_port = int(os.getenv("NOVNC_PORT", "8002"))
        self.script_path = Path(__file__).parent / "docker" / "desktop_launch.sh"

    async def start(self) -> bool:
        """Start the desktop by launching desktop_launch.sh script."""
        if not self.script_path.exists():
            logger.warning("desktop_launch.sh not found; desktop disabled")
            return False

        if self.is_running():
            logger.info("Desktop already running")
            return True

        try:
            # Launch the desktop_launch.sh script
            logger.info("Starting desktop via %s", self.script_path)
            self._proc = await asyncio.create_subprocess_exec(
                str(self.script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            # Wait a bit for the desktop to start
            await asyncio.sleep(2)
            
            if self.is_running():
                logger.info("Desktop started successfully")
                return True
            else:
                logger.error("Desktop failed to start")
                return False

        except Exception as e:
            logger.error("Failed to start desktop: %s", e)
            return False

    async def stop(self) -> None:
        """Stop the desktop process."""
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=5)
                logger.info("Desktop stopped")
            except asyncio.TimeoutError:
                logger.warning("Desktop did not stop gracefully, killing process")
                self._proc.kill()
                await self._proc.wait()
            except Exception as e:
                logger.error("Error stopping desktop: %s", e)
            finally:
                self._proc = None

    def is_running(self) -> bool:
        """Check if desktop is running."""
        if self._proc and self._proc.returncode is None:
            return True
        
        # Check if VNC server is running
        try:
            result = subprocess.run(
                ["pgrep", "-f", "Xvnc"],
                capture_output=True, text=True, timeout=3
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_vnc_url(self, base: str = "http://localhost") -> Optional[str]:
        """Get the noVNC URL for desktop access."""
        if not self.is_running():
            return None
        return f"{base}:{self.novnc_port}/vnc.html?autoconnect=1&resize=remote"


# ------- module-level accessor -------

_desktop_service: Optional[DesktopService] = None

def get_desktop_service() -> Optional[DesktopService]:
    """Get the desktop service instance if VNC is enabled."""
    global _desktop_service
    if _desktop_service is None:
        from openhands.agent_server.config import get_default_config
        
        config = get_default_config()
        
        if not config.enable_vnc:
            logger.info("VNC desktop is disabled in configuration")
            return None
        else:
            _desktop_service = DesktopService()
    return _desktop_service
