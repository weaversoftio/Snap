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

# Update Helm values.yaml with new image repo and tag
VALUES_FILE="$CHART_DIR/values.yaml"
if [[ ! -f "$VALUES_FILE" ]]; then
  echo "ERROR: values.yaml not found at $VALUES_FILE" >&2
  exit 1
fi

# Cross-platform sed in-place
sed_i() {
  if sed --version >/dev/null 2>&1; then
    sed -i "$@"
  else
    sed -i '' "$@"
  fi
}

# Ensure keys exist and update them
# repository
if grep -q '^image:\s*$' "$VALUES_FILE"; then
  :
fi

sed_i "s|^\s*repository:.*$|  repository: '$REGISTRY/$IMAGE_NAME'|" "$VALUES_FILE"
sed_i "s|^\s*tag:.*$|  tag: '$IMAGE_TAG'|" "$VALUES_FILE"

# Deploy or upgrade with Helm
if command -v helm >/dev/null 2>&1; then
  echo "Deploying with Helm release '$RELEASE_NAME' to namespace '$NAMESPACE'"
  helm upgrade --install "$RELEASE_NAME" "$CHART_DIR" \
    --namespace "$NAMESPACE" --create-namespace
else
  echo "helm not found; skipping Helm deployment. Chart updated with image $FULL_IMAGE"
fi

echo "Done. Image: $FULL_IMAGE"
