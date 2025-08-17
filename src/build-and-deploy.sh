#!/bin/bash

set -euo pipefail

# Configuration via env vars or flags
REGISTRY="${REGISTRY:-}"
IMAGE_NAME="${IMAGE_NAME:-snap-operator}"
IMAGE_TAG="${IMAGE_TAG:-}"
NAMESPACE="${NAMESPACE:-snap}"
RELEASE_NAME="${RELEASE_NAME:-snap-operator}"
CHART_DIR="${CHART_DIR:-../helmchart}"
DOCKERFILE_DIR="${DOCKERFILE_DIR:-.}"

usage() {
  echo "Usage: REGISTRY=<registry> [IMAGE_NAME=name] [IMAGE_TAG=tag] [NAMESPACE=ns] [RELEASE_NAME=name] ./build-and-deploy.sh"
  echo "  REGISTRY (required): e.g. docker.io/youruser, quay.io/yourorg, ghcr.io/yourorg"
}

if [[ -z "$REGISTRY" ]]; then
  echo "ERROR: REGISTRY is required" >&2
  usage
  exit 1
fi

# Default tag to git sha + date if not provided
if [[ -z "$IMAGE_TAG" ]]; then
  if command -v git >/dev/null 2>&1; then
    GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "nogit")
  else
    GIT_SHA="nogit"
  fi
  IMAGE_TAG="$(date +%Y%m%d%H%M%S)-$GIT_SHA"
fi

FULL_IMAGE="$REGISTRY/$IMAGE_NAME:$IMAGE_TAG"

echo "Building image: $FULL_IMAGE"
docker build -t "$FULL_IMAGE" "$DOCKERFILE_DIR"

echo "Pushing image: $FULL_IMAGE"
docker push "$FULL_IMAGE"


echo "Done. Image: $FULL_IMAGE"
