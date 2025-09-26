#!/usr/bin/env bash
set -euo pipefail

# === Environment ===
export DISPLAY="${DISPLAY:-:1}"
export USER="${USER:-${USERNAME:-openhands}}"
export HOME="${HOME:-/home/${USERNAME:-openhands}}"
export NOVNC_PORT="${NOVNC_PORT:-8002}"
export VNC_GEOMETRY="${VNC_GEOMETRY:-1280x800}"

# === Ensure home + dirs ===
mkdir -p "$HOME/.vnc" "$HOME/.config" "$HOME/Downloads"
chown -R "$USER":"$USER" "$HOME" || true

# === Ensure VNC password ===
if [ ! -f "$HOME/.vnc/passwd" ]; then
  if command -v vncpasswd >/dev/null 2>&1; then
    echo "openhands" | vncpasswd -f > "$HOME/.vnc/passwd"
    chmod 600 "$HOME/.vnc/passwd"
    chown "$USER":"$USER" "$HOME/.vnc/passwd" || true
  else
    echo "ERROR: vncpasswd not found. Install tigervnc-tools or pre-provide $HOME/.vnc/passwd"
    exit 1
  fi
fi

# === Ensure xstartup runs XFCE ===
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

# === Start TigerVNC ===
if ! pgrep -f "Xvnc .*${DISPLAY}" >/dev/null 2>&1; then
  echo "Starting TigerVNC server on ${DISPLAY} (${VNC_GEOMETRY})..."
  vncserver "${DISPLAY}" -geometry "${VNC_GEOMETRY}" -depth 24 || true
fi

# === Start noVNC/websockify ===
if ! pgrep -f "websockify .* ${NOVNC_PORT} " >/dev/null 2>&1; then
  echo "Starting noVNC on 0.0.0.0:${NOVNC_PORT} -> localhost:5901 ..."
  websockify --daemon --web=/usr/share/novnc/ 0.0.0.0:${NOVNC_PORT} 127.0.0.1:5901
fi

echo "noVNC ready: http://localhost:${NOVNC_PORT}/ (connects to ${DISPLAY})"

# === Start the agent server ===
echo "Launching agent: $*"
exec "$@"
