#!/bin/sh

# API_URL and WS_URL are optional - if not set or empty, the UI will use relative paths
# This allows the app to work behind a reverse proxy without configuration
# For reverse proxy setups, set API_URL="" and WS_URL="" (empty strings)

# Set defaults to empty if not provided (for reverse proxy mode)
API_URL=${API_URL:-}
WS_URL=${WS_URL:-}

# Debug output
echo "docker-entrypoint.sh: API_URL='$API_URL'"
echo "docker-entrypoint.sh: WS_URL='$WS_URL'"

# For development: ensure dependencies are installed (volume mounts may overwrite node_modules)
# Use the global yarn (not corepack) and ensure dependencies are installed
if [ -f /app/package.json ]; then
    # Ensure we're using yarn 1.x from /usr/local/bin, not corepack
    export PATH="/usr/local/bin:$PATH"
    YARN_VERSION=$(yarn --version 2>/dev/null || echo "unknown")
    echo "docker-entrypoint.sh: Using yarn version: $YARN_VERSION"
    
    # Install dependencies if node_modules is missing, incomplete, or react-scripts is missing
    # Check multiple conditions - if any fail, reinstall
    NEED_INSTALL=false
    if [ ! -d /app/node_modules ]; then
        echo "docker-entrypoint.sh: node_modules directory missing"
        NEED_INSTALL=true
    elif [ ! -f /app/node_modules/.yarn-integrity ] && [ ! -f /app/node_modules/.package-lock.json ]; then
        echo "docker-entrypoint.sh: node_modules appears incomplete (no integrity file)"
        NEED_INSTALL=true
    elif [ ! -f /app/node_modules/.bin/react-scripts ]; then
        echo "docker-entrypoint.sh: react-scripts binary missing"
        NEED_INSTALL=true
    fi
    
    if [ "$NEED_INSTALL" = "true" ]; then
        echo "docker-entrypoint.sh: Installing dependencies..."
        cd /app && yarn install --ignore-engines
        echo "docker-entrypoint.sh: Dependency installation complete"
    else
        echo "docker-entrypoint.sh: Dependencies already installed"
    fi
fi

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
if [ -f /opt/app-root/src/index.html ]; then
    echo "docker-entrypoint.sh: Replacing placeholders in /opt/app-root/src/index.html"
    API_URL_VALUE="${API_URL:-}"
    WS_URL_VALUE="${WS_URL:-}"
    
    # Replace placeholders - try multiple patterns to handle different cases
    # Pattern 1: Direct placeholder replacement
    if [ -z "$API_URL_VALUE" ]; then
        # Empty string - replace with empty string (multiple patterns)
        sed -i "s|'%REACT_APP_API_URL%'|''|g" /opt/app-root/src/index.html
        sed -i "s|\"%REACT_APP_API_URL%\"|\"\"|g" /opt/app-root/src/index.html
        sed -i "s|%REACT_APP_API_URL%||g" /opt/app-root/src/index.html
    else
        # Has value - replace placeholder (escape special chars for sed)
        ESCAPED_API_URL=$(echo "$API_URL_VALUE" | sed 's/[[\.*^$()+?{|]/\\&/g')
        sed -i "s|%REACT_APP_API_URL%|$ESCAPED_API_URL|g" /opt/app-root/src/index.html
    fi
    
    if [ -z "$WS_URL_VALUE" ]; then
        # Empty string - replace with empty string (multiple patterns)
        sed -i "s|'%REACT_APP_WS_URL%'|''|g" /opt/app-root/src/index.html
        sed -i "s|\"%REACT_APP_WS_URL%\"|\"\"|g" /opt/app-root/src/index.html
        sed -i "s|%REACT_APP_WS_URL%||g" /opt/app-root/src/index.html
    else
        # Has value - replace placeholder (escape special chars for sed)
        ESCAPED_WS_URL=$(echo "$WS_URL_VALUE" | sed 's/[[\.*^$()+?{|]/\\&/g')
        sed -i "s|%REACT_APP_WS_URL%|$ESCAPED_WS_URL|g" /opt/app-root/src/index.html
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
