#!/usr/bin/env bash
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
