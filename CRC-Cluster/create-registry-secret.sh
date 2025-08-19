#!/bin/bash

# Script to create a Docker registry secret for Nexus
# Replace these values with your actual Nexus credentials

NAMESPACE="snap"
REGISTRY="192.168.33.204:8082"
USERNAME="k8s"
PASSWORD="k8s"

echo "Creating Docker registry secret for Nexus registry: $REGISTRY"
echo "Namespace: $NAMESPACE"
echo "Username: $USERNAME"
echo ""

# Create the secret
oc create secret docker-registry nexus-registry-secret \
  --docker-server="$REGISTRY" \
  --docker-username="$USERNAME" \
  --docker-password="$PASSWORD" \
  --namespace="$NAMESPACE"

echo ""
echo "Secret created successfully!"
echo "Now you need to update your deployment to use this secret."
echo ""
echo "You can either:"
echo "1. Add imagePullSecrets to your deployment manually, or"
echo "2. Update the Helm chart to include this secret"
