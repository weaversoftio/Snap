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

# Generate runtime-config.js from template
# This approach avoids modifying source files (index.html) which are mounted as volumes in dev mode
API_URL_VALUE="${API_URL:-}"
WS_URL_VALUE="${WS_URL:-}"

# Escape values for JavaScript double-quoted string literals
# Must escape backslashes first, then double quotes
escape_js_string() {
    if [ -z "$1" ]; then
        echo ""
    else
        # Use printf %q for safe escaping, then manually handle for JS strings
        # First escape backslashes, then escape double quotes
        printf '%s' "$1" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g'
    fi
}

ESCAPED_API_URL=$(escape_js_string "$API_URL_VALUE")
ESCAPED_WS_URL=$(escape_js_string "$WS_URL_VALUE")

# Escape for sed replacement (escape & and backslashes in replacement string)
escape_sed_replacement() {
    printf '%s' "$1" | sed 's/\\/\\\\/g' | sed 's/&/\\&/g'
}

SED_ESCAPED_API_URL=$(escape_sed_replacement "$ESCAPED_API_URL")
SED_ESCAPED_WS_URL=$(escape_sed_replacement "$ESCAPED_WS_URL")

# Generate runtime-config.js for development (in public folder)
if [ -f /app/public/runtime-config.template.js ]; then
    echo "docker-entrypoint.sh: Generating runtime-config.js from template (development)"
    sed "s|\${API_URL}|$SED_ESCAPED_API_URL|g" /app/public/runtime-config.template.js | \
    sed "s|\${WS_URL}|$SED_ESCAPED_WS_URL|g" > /app/public/runtime-config.js
    echo "docker-entrypoint.sh: runtime-config.js generated successfully"
fi

# Generate runtime-config.js for production (in /opt/app-root/src)
if [ -f /opt/app-root/src/runtime-config.template.js ]; then
    echo "docker-entrypoint.sh: Generating runtime-config.js from template (production)"
    sed "s|\${API_URL}|$SED_ESCAPED_API_URL|g" /opt/app-root/src/runtime-config.template.js | \
    sed "s|\${WS_URL}|$SED_ESCAPED_WS_URL|g" > /opt/app-root/src/runtime-config.js
    chmod 666 /opt/app-root/src/runtime-config.js
    echo "docker-entrypoint.sh: runtime-config.js generated successfully"
fi

# Also generate in /tmp for production (as fallback)
if [ -f /tmp/runtime-config.template.js ]; then
    echo "docker-entrypoint.sh: Generating runtime-config.js from template (production /tmp)"
    sed "s|\${API_URL}|$SED_ESCAPED_API_URL|g" /tmp/runtime-config.template.js | \
    sed "s|\${WS_URL}|$SED_ESCAPED_WS_URL|g" > /tmp/runtime-config.js
    chmod 666 /tmp/runtime-config.js
    echo "docker-entrypoint.sh: runtime-config.js generated successfully in /tmp"
fi

# Execute CMD
exec "$@"
