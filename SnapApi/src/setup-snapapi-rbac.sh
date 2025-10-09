#!/bin/bash

# SnapAPI RBAC Setup Script for OpenShift
# This script applies the RBAC configuration and provides a summary

set -e

echo "=========================================="
echo "SnapAPI RBAC Setup for OpenShift"
echo "=========================================="

# Check if oc is available
if ! command -v oc &> /dev/null; then
    echo "Error: oc command not found. Please ensure OpenShift CLI is installed."
    exit 1
fi

# Check if we're logged in to OpenShift
if ! oc whoami &> /dev/null; then
    echo "Error: Not logged in to OpenShift. Please run 'oc login' first."
    exit 1
fi

echo "Current user: $(oc whoami)"
echo "Current project: $(oc project -q)"
echo ""

# Create namespace if it doesn't exist
echo "Creating namespace 'snap' if it doesn't exist..."
oc new-project snap --skip-config-write 2>/dev/null || echo "Namespace 'snap' already exists or created successfully"
echo ""

# Apply RBAC configuration
echo "Applying RBAC configuration..."
oc apply -f snapapi-rbac.yaml
echo ""

# Wait a moment for resources to be created
sleep 2

# Create permanent token
echo "Creating permanent token (1 year duration)..."
TOKEN=$(oc create token snapapi-serviceaccount -n snap --duration=8760h)
echo ""

# Get API server URL
echo "Getting cluster information..."
API_SERVER=$(oc cluster-info | grep "Kubernetes control plane" | awk '{print $7}')
echo ""

# Verify permissions
echo "Verifying service account permissions..."
echo -n "Can get pods: "
oc auth can-i get pods --as=system:serviceaccount:snap:snapapi-serviceaccount 2>/dev/null && echo "YES" || echo "NO"

echo -n "Can get nodes: "
oc auth can-i get nodes --as=system:serviceaccount:snap:snapapi-serviceaccount 2>/dev/null && echo "YES" || echo "NO"

echo -n "Can create mutatingwebhookconfigurations: "
oc auth can-i create mutatingwebhookconfigurations --as=system:serviceaccount:snap:snapapi-serviceaccount 2>/dev/null && echo "YES" || echo "NO"

echo -n "Can use privileged SCC: "
oc auth can-i use scc/privileged --as=system:serviceaccount:snap:snapapi-serviceaccount 2>/dev/null && echo "YES" || echo "NO"
echo ""

# Print summary
echo "=========================================="
echo "SnapAPI Configuration Summary"
echo "=========================================="
echo "KubeApi: $API_SERVER"
echo "Token: $TOKEN"
echo ""
echo "Service Account: snapapi-serviceaccount"
echo "Namespace: snap"
echo "Cluster Role: snapapi-clusterrole"
echo "=========================================="
echo ""

# Save configuration to file
echo "Saving configuration to snapapi-config.json..."
cat > snapapi-config.json << EOF
{
  "cluster_config_details": {
    "kube_api_url": "$API_SERVER",
    "token": "$TOKEN"
  },
  "name": "$(oc config current-context | cut -d'/' -f1)"
}
EOF

echo "Configuration saved to: snapapi-config.json"
echo ""
echo "You can now use this configuration in your SnapAPI cluster setup."
echo "=========================================="
