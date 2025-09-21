#!/bin/sh

# Replace environment variables in JavaScript files
if [ -n "$AGENT_SERVER_URL" ]; then
    echo "Configuring agent server URL: $AGENT_SERVER_URL"
    # This is a simple approach - in production you might want a more sophisticated config system
    sed -i "s|http://localhost:8000|$AGENT_SERVER_URL|g" /usr/share/nginx/html/app.js
    sed -i "s|ws://localhost:8000|${AGENT_SERVER_URL/http/ws}|g" /usr/share/nginx/html/app.js
fi

# Execute the original command
exec "$@"