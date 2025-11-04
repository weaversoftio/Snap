#!/bin/sh

# Replace API_URL in config.js (now in /tmp)
sed -i "s|\${API_URL}|$API_URL|g" /tmp/config.js
sed -i "s|\${WS_URL}|$WS_URL|g" /tmp/config.js

# Replace REACT_APP_API_URL and REACT_APP_WS_URL in index.html
if [ -f /usr/share/nginx/html/index.html ]; then
    sed -i "s|%REACT_APP_API_URL%|${API_URL:-http://192.168.33.209:8000}|g" /usr/share/nginx/html/index.html
    sed -i "s|%REACT_APP_WS_URL%|${WS_URL:-ws://192.168.33.209:8000}|g" /usr/share/nginx/html/index.html
fi

# Execute CMD
exec "$@"
