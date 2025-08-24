#!/bin/sh

# Replace API_URL in config.js (now in /tmp)
sed -i "s|\${API_URL}|$API_URL|g" /tmp/config.js
sed -i "s|\${WS_URL}|$WS_URL|g" /tmp/config.js

# Execute CMD
exec "$@"
