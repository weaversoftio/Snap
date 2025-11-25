#!/bin/sh

# Check if required environment variables are set (should have defaults from docker-compose, but validate)
if [ -z "$API_URL" ] || [ "$API_URL" = "" ]; then
    echo "ERROR: API_URL environment variable is not set"
    exit 1
fi

if [ -z "$WS_URL" ] || [ "$WS_URL" = "" ]; then
    echo "ERROR: WS_URL environment variable is not set"
    exit 1
fi

# Replace API_URL in config.js (now in /tmp)
sed -i "s|\${API_URL}|$API_URL|g" /tmp/config.js
sed -i "s|\${WS_URL}|$WS_URL|g" /tmp/config.js

# Replace REACT_APP_API_URL and REACT_APP_WS_URL in index.html
if [ -f /usr/share/nginx/html/index.html ]; then
    sed -i "s|%REACT_APP_API_URL%|$API_URL|g" /usr/share/nginx/html/index.html
    sed -i "s|%REACT_APP_WS_URL%|$WS_URL|g" /usr/share/nginx/html/index.html
fi

# Execute CMD
exec "$@"
