"""Desktop service for launching VNC desktop via desktop_launch.sh script."""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

from openhands.sdk.logger import get_logger


logger = get_logger(__name__)

DESKTOP_LAUNCH_SCRIPT = """#!/usr/bin/env bash
set -euo pipefail

# --- Env ---
export DISPLAY="${DISPLAY:-:1}"
export USER="${USER:-${USERNAME:-openhands}}"
export HOME="${HOME:-/home/${USERNAME:-openhands}}"
export NOVNC_PORT="${NOVNC_PORT:-8002}"
export VNC_GEOMETRY="${VNC_GEOMETRY:-1280x800}"
NOVNC_PROXY="/usr/share/novnc/utils/novnc_proxy"
NOVNC_WEB="${NOVNC_WEB:-/opt/novnc-web}"

# --- Dirs & ownership (idempotent, user-writable only) ---
mkdir -p "$HOME/.vnc" "$HOME/.config" "$HOME/Downloads"
chown -R "$USER":"$USER" "$HOME" || true

# --- VNC password ---
if [ ! -f "$HOME/.vnc/passwd" ]; then
  if command -v vncpasswd >/dev/null 2>&1; then
    echo "openhands" | vncpasswd -f > "$HOME/.vnc/passwd"
    chmod 600 "$HOME/.vnc/passwd"
    chown "$USER":"$USER" "$HOME/.vnc/passwd" || true
  else
    echo "ERROR: vncpasswd not found (install tigervnc-tools)"; exit 1
  fi
fi

# --- xstartup for XFCE ---
XSTARTUP="$HOME/.vnc/xstartup"
if [ ! -f "$XSTARTUP" ]; then
  cat > "$XSTARTUP" <<'EOS'
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
exec startxfce4
EOS
  chmod +x "$XSTARTUP"
  chown "$USER":"$USER" "$XSTARTUP" || true
fi

# --- Start TigerVNC (bind to loopback; novnc proxies) ---
if ! pgrep -f "Xvnc .*${DISPLAY}" >/dev/null 2>&1; then
  echo "Starting TigerVNC on ${DISPLAY} (${VNC_GEOMETRY})..."
  vncserver "${DISPLAY}" -geometry "${VNC_GEOMETRY}" -depth 24 -localhost yes || true
fi

# --- Start noVNC proxy (foreground tool → background it) ---
if ! pgrep -f "[n]ovnc_proxy .*--listen .*${NOVNC_PORT}" >/dev/null 2>&1; then
  echo "Starting noVNC proxy on 0.0.0.0:${NOVNC_PORT} -> 127.0.0.1:5901 ..."
  nohup "${NOVNC_PROXY}" \
        --listen "0.0.0.0:${NOVNC_PORT}" \
        --vnc "127.0.0.1:5901" \
        --web "${NOVNC_WEB}"
fi

echo "noVNC: http://localhost:${NOVNC_PORT}/vnc.html?autoconnect=1&resize=remote"

# --- Start the agent ---
echo "Launching agent: $*"
exec "$@"
"""


class DesktopService:
    """Simple desktop service that launches desktop_launch.sh script."""

    def __init__(self):
        self._proc: asyncio.subprocess.Process | None = None
        self.novnc_port = int(os.getenv("NOVNC_PORT", "8002"))
        self.script_path = Path("/tmp/desktop_launch.sh")
        with open(self.script_path, "w") as f:
            f.write(DESKTOP_LAUNCH_SCRIPT)
        os.chmod(self.script_path, 0o755)

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
            except TimeoutError:
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
                ["pgrep", "-f", "Xvnc"], capture_output=True, text=True, timeout=3
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_vnc_url(self, base: str = "http://localhost:8003") -> str | None:
        """Get the noVNC URL for desktop access."""
        if not self.is_running():
            return None
        return f"{base}/vnc.html?autoconnect=1&resize=remote"


# ------- module-level accessor -------

_desktop_service: DesktopService | None = None


def get_desktop_service() -> DesktopService | None:
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
