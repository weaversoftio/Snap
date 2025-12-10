#!/bin/sh

# API_URL and WS_URL are optional - if not set or empty, the UI will use relative paths
# This allows the app to work behind a reverse proxy without configuration
# For reverse proxy setups, set API_URL="" and WS_URL="" (empty strings)
# For direct access, set them to the full URLs (e.g., http://192.168.33.209:8000)

# Set defaults to empty if not provided (for reverse proxy mode)
API_URL=${API_URL:-}
WS_URL=${WS_URL:-}

# Debug output
echo "docker-entrypoint.sh: API_URL='$API_URL'"
echo "docker-entrypoint.sh: WS_URL='$WS_URL'"

# Replace API_URL in config.js (production - now in /tmp)
if [ -f /tmp/config.js ]; then
    sed -i "s|\${API_URL}|$API_URL|g" /tmp/config.js
    sed -i "s|\${WS_URL}|$WS_URL|g" /tmp/config.js
fi

# Replace API_URL in config.js (development - in public folder)
if [ -f /app/public/config.js ]; then
    sed -i "s|\${API_URL}|$API_URL|g" /app/public/config.js
    sed -i "s|\${WS_URL}|$WS_URL|g" /app/public/config.js
fi

# Replace REACT_APP_API_URL and REACT_APP_WS_URL in index.html (production)
if [ -f /usr/share/nginx/html/index.html ]; then
    echo "docker-entrypoint.sh: Replacing placeholders in /usr/share/nginx/html/index.html"
    API_URL_VALUE="${API_URL:-}"
    WS_URL_VALUE="${WS_URL:-}"
    
    # Replace placeholders - try multiple patterns to handle different cases
    # Pattern 1: Direct placeholder replacement
    if [ -z "$API_URL_VALUE" ]; then
        # Empty string - replace with empty string (multiple patterns)
        sed -i "s|'%REACT_APP_API_URL%'|''|g" /usr/share/nginx/html/index.html
        sed -i "s|\"%REACT_APP_API_URL%\"|\"\"|g" /usr/share/nginx/html/index.html
        sed -i "s|%REACT_APP_API_URL%||g" /usr/share/nginx/html/index.html
    else
        # Has value - replace placeholder (escape special chars for sed)
        ESCAPED_API_URL=$(echo "$API_URL_VALUE" | sed 's/[[\.*^$()+?{|]/\\&/g')
        sed -i "s|%REACT_APP_API_URL%|$ESCAPED_API_URL|g" /usr/share/nginx/html/index.html
    fi
    
    if [ -z "$WS_URL_VALUE" ]; then
        # Empty string - replace with empty string (multiple patterns)
        sed -i "s|'%REACT_APP_WS_URL%'|''|g" /usr/share/nginx/html/index.html
        sed -i "s|\"%REACT_APP_WS_URL%\"|\"\"|g" /usr/share/nginx/html/index.html
        sed -i "s|%REACT_APP_WS_URL%||g" /usr/share/nginx/html/index.html
    else
        # Has value - replace placeholder (escape special chars for sed)
        ESCAPED_WS_URL=$(echo "$WS_URL_VALUE" | sed 's/[[\.*^$()+?{|]/\\&/g')
        sed -i "s|%REACT_APP_WS_URL%|$ESCAPED_WS_URL|g" /usr/share/nginx/html/index.html
    fi
    
    echo "docker-entrypoint.sh: Placeholder replacement complete"
fi

# Replace REACT_APP_API_URL and REACT_APP_WS_URL in index.html (development)
if [ -f /app/public/index.html ]; then
    echo "docker-entrypoint.sh: Replacing placeholders in /app/public/index.html"
    API_URL_VALUE="${API_URL:-}"
    WS_URL_VALUE="${WS_URL:-}"
    
    # Replace placeholders - try multiple patterns to handle different cases
    if [ -z "$API_URL_VALUE" ]; then
        # Empty string - replace with empty string (multiple patterns)
        sed -i "s|'%REACT_APP_API_URL%'|''|g" /app/public/index.html
        sed -i "s|\"%REACT_APP_API_URL%\"|\"\"|g" /app/public/index.html
        sed -i "s|%REACT_APP_API_URL%||g" /app/public/index.html
    else
        # Has value - replace placeholder (escape special chars for sed)
        ESCAPED_API_URL=$(echo "$API_URL_VALUE" | sed 's/[[\.*^$()+?{|]/\\&/g')
        sed -i "s|%REACT_APP_API_URL%|$ESCAPED_API_URL|g" /app/public/index.html
    fi
    
    if [ -z "$WS_URL_VALUE" ]; then
        # Empty string - replace with empty string (multiple patterns)
        sed -i "s|'%REACT_APP_WS_URL%'|''|g" /app/public/index.html
        sed -i "s|\"%REACT_APP_WS_URL%\"|\"\"|g" /app/public/index.html
        sed -i "s|%REACT_APP_WS_URL%||g" /app/public/index.html
    else
        # Has value - replace placeholder (escape special chars for sed)
        ESCAPED_WS_URL=$(echo "$WS_URL_VALUE" | sed 's/[[\.*^$()+?{|]/\\&/g')
        sed -i "s|%REACT_APP_WS_URL%|$ESCAPED_WS_URL|g" /app/public/index.html
    fi
fi

# Execute CMD
exec "$@"
