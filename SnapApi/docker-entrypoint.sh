#!/bin/bash
set -e

# Fix permissions for checkpoints directory
# This is needed because Docker volumes are often owned by root
if [ -d "/app/checkpoints" ]; then
    echo "Fixing permissions for /app/checkpoints directory..."
    chown -R 669:0 /app/checkpoints || true
    chmod -R 775 /app/checkpoints || true
else
    echo "Creating /app/checkpoints directory..."
    mkdir -p /app/checkpoints
    chown -R 669:0 /app/checkpoints
    chmod -R 775 /app/checkpoints
fi

# Fix permissions for config directory if it exists
if [ -d "/app/config" ]; then
    echo "Fixing permissions for /app/config directory..."
    chown -R 669:0 /app/config || true
    chmod -R 775 /app/config || true
fi

# Switch to snap user and execute the command
# runuser is standard in RHEL/UBI images
exec runuser -u snap -- "$@"

