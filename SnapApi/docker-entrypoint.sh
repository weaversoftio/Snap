#!/bin/bash
set -e

# #region agent log
echo "{\"sessionId\":\"debug-session\",\"runId\":\"initial\",\"hypothesisId\":\"H1,H3,H4\",\"location\":\"docker-entrypoint.sh:5\",\"message\":\"Entrypoint started\",\"data\":{\"user\":\"$(whoami)\",\"uid\":\"$(id -u)\",\"gid\":\"$(id -g)\",\"euid\":\"$(id -u)\"},\"timestamp\":$(date +%s)000}" >> /tmp/debug.log
# #endregion

# Fix permissions for checkpoints directory
# This is needed because Docker volumes are often owned by root
if [ -d "/app/checkpoints" ]; then
    echo "docker-entrypoint.sh: Fixing permissions for /app/checkpoints directory..."
    # #region agent log
    echo "{\"sessionId\":\"debug-session\",\"runId\":\"initial\",\"hypothesisId\":\"H2\",\"location\":\"docker-entrypoint.sh:13\",\"message\":\"Before chown checkpoints\",\"data\":{\"dir_exists\":true,\"checkpoints_perms\":\"$(ls -ld /app/checkpoints 2>&1)\"},\"timestamp\":$(date +%s)000}" >> /tmp/debug.log
    # #endregion
    chown -R 669:0 /app/checkpoints 2>/dev/null || true
    # #region agent log
    echo "{\"sessionId\":\"debug-session\",\"runId\":\"initial\",\"hypothesisId\":\"H2\",\"location\":\"docker-entrypoint.sh:17\",\"message\":\"After chown checkpoints\",\"data\":{\"exit_code\":\"$?\",\"checkpoints_perms\":\"$(ls -ld /app/checkpoints 2>&1)\"},\"timestamp\":$(date +%s)000}" >> /tmp/debug.log
    # #endregion
    chmod -R 775 /app/checkpoints 2>/dev/null || true
else
    echo "docker-entrypoint.sh: Creating /app/checkpoints directory..."
    mkdir -p /app/checkpoints
    chown -R 669:0 /app/checkpoints 2>/dev/null || true
    chmod -R 775 /app/checkpoints 2>/dev/null || true
fi

# Fix permissions for config directory if it exists
if [ -d "/app/config" ]; then
    echo "docker-entrypoint.sh: Fixing permissions for /app/config directory..."
    # #region agent log
    echo "{\"sessionId\":\"debug-session\",\"runId\":\"initial\",\"hypothesisId\":\"H2\",\"location\":\"docker-entrypoint.sh:28\",\"message\":\"Before chown config\",\"data\":{\"dir_exists\":true,\"config_perms\":\"$(ls -ld /app/config 2>&1)\"},\"timestamp\":$(date +%s)000}" >> /tmp/debug.log
    # #endregion
    chown -R 669:0 /app/config 2>/dev/null || true
    chmod -R 775 /app/config 2>/dev/null || true
fi

# Execute the command (already running as snap user due to USER directive in Dockerfile)
# #region agent log
echo "{\"sessionId\":\"debug-session\",\"runId\":\"post-fix\",\"hypothesisId\":\"H1,H4\",\"location\":\"docker-entrypoint.sh:38\",\"message\":\"Before exec\",\"data\":{\"current_user\":\"$(whoami)\",\"uid\":\"$(id -u)\",\"command\":\"$@\"},\"timestamp\":$(date +%s)000}" >> /tmp/debug.log
# #endregion
exec "$@"

