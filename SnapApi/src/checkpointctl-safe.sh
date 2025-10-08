#!/bin/bash

# Safe checkpointctl inspect wrapper that handles environment variable parsing errors
# Usage: ./checkpointctl-safe.sh <checkpoint_file> [additional_flags]

set -e

CHECKPOINT_FILE="$1"
shift
ADDITIONAL_FLAGS="$@"

if [ -z "$CHECKPOINT_FILE" ]; then
    echo "Usage: $0 <checkpoint_file> [additional_flags]"
    echo "Example: $0 /path/to/checkpoint.tar --format json"
    exit 1
fi

if [ ! -f "$CHECKPOINT_FILE" ]; then
    echo "Error: Checkpoint file '$CHECKPOINT_FILE' does not exist"
    exit 1
fi

echo "Attempting full checkpoint inspection..."

# Try with --all flag first
if checkpointctl inspect "$CHECKPOINT_FILE" --all $ADDITIONAL_FLAGS 2>/dev/null; then
    echo "Full inspection completed successfully"
    exit 0
fi

# Check if the error is related to environment variable parsing
ERROR_OUTPUT=$(checkpointctl inspect "$CHECKPOINT_FILE" --all $ADDITIONAL_FLAGS 2>&1 || true)

if echo "$ERROR_OUTPUT" | grep -q "invalid environment variable.*nginx.*daemon off"; then
    echo "Detected environment variable parsing error. Falling back to safe inspection flags..."
    echo ""
    
    # Try individual safe flags
    echo "=== Basic Checkpoint Information ==="
    checkpointctl inspect "$CHECKPOINT_FILE" $ADDITIONAL_FLAGS
    
    echo ""
    echo "=== Process Tree (without environment variables) ==="
    checkpointctl inspect "$CHECKPOINT_FILE" --ps-tree $ADDITIONAL_FLAGS
    
    echo ""
    echo "=== Process Tree with Command Line Arguments ==="
    checkpointctl inspect "$CHECKPOINT_FILE" --ps-tree-cmd $ADDITIONAL_FLAGS
    
    echo ""
    echo "=== Metadata ==="
    checkpointctl inspect "$CHECKPOINT_FILE" --metadata $ADDITIONAL_FLAGS
    
    echo ""
    echo "=== Mounts ==="
    checkpointctl inspect "$CHECKPOINT_FILE" --mounts $ADDITIONAL_FLAGS
    
    echo ""
    echo "=== File Descriptors ==="
    checkpointctl inspect "$CHECKPOINT_FILE" --files $ADDITIONAL_FLAGS
    
    echo ""
    echo "=== Sockets ==="
    checkpointctl inspect "$CHECKPOINT_FILE" --sockets $ADDITIONAL_FLAGS
    
    echo ""
    echo "=== Statistics ==="
    checkpointctl inspect "$CHECKPOINT_FILE" --stats $ADDITIONAL_FLAGS
    
    echo ""
    echo "Note: Environment variables could not be displayed due to parsing error in checkpoint data"
    echo "This is likely caused by nginx command line arguments being stored incorrectly as environment variables"
    
else
    echo "Error occurred but not related to environment variable parsing:"
    echo "$ERROR_OUTPUT"
    exit 1
fi
