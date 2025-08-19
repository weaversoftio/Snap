#!/bin/bash

set -euo pipefail

# Configuration via env vars or flags
REGISTRY="${REGISTRY:-192.168.33.204:8082}"
IMAGE_NAME="${IMAGE_NAME:-snap-watcher}"
IMAGE_TAG="${IMAGE_TAG:-}"
NAMESPACE="${NAMESPACE:-snap}"
RELEASE_NAME="${RELEASE_NAME:-snap-watcher}"
CHART_DIR="${CHART_DIR:-../helmchart}"
DOCKERFILE_DIR="${DOCKERFILE_DIR:-.}"
DEPLOYMENT_FILE="${DEPLOYMENT_FILE:-yamls/deployment.yaml}"
RBAC_FILE="${RBAC_FILE:-yamls/rbac.yaml}"

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

echo "Deleting existing deployment..."
oc delete -f "$DEPLOYMENT_FILE" --ignore-not-found=true
echo " "

echo "Deleting existing RBAC..."
oc delete -f "$RBAC_FILE" --ignore-not-found=true
echo " "

echo "Waiting for old pods to terminate..."
while oc get pods -n "$NAMESPACE" -l app=$IMAGE_NAME 2>/dev/null | grep -qvE 'NAME|Terminating'; do
  echo "  Still terminating..."
  sleep 3
done
echo " "


echo "Building image: $FULL_IMAGE"
podman build -t "$FULL_IMAGE" "$DOCKERFILE_DIR"
echo " "

echo "Pushing image: $FULL_IMAGE"
podman push "$FULL_IMAGE"
echo " "

echo "Updating $DEPLOYMENT_FILE with new image..."
sed -i.bak "s|image: .*|image: $FULL_IMAGE|" "$DEPLOYMENT_FILE"
echo " "

echo "Applying updated deployment..."
oc apply -f "$DEPLOYMENT_FILE"
echo " "

echo "Applying updated rbac..."
oc apply -f "$RBAC_FILE"
echo " "

echo "Waiting for new pod to be ready..."
while true; do
  POD=$(oc get pods -n "$NAMESPACE" -l app=$IMAGE_NAME -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
  if [[ -n "$POD" ]]; then
    STATUS=$(oc get pod "$POD" -n "$NAMESPACE" -o jsonpath='{.status.phase}')
    if [[ "$STATUS" == "Running" ]]; then
      echo "Pod $POD is running"
      break
    fi
  fi
  echo "  Waiting for pod..."
  sleep 3
done
echo " "

echo "Tailing logs from pod $POD..."
oc logs -n "$NAMESPACE" "$POD" -f