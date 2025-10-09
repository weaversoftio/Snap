#!/bin/bash

# One-line RBAC setup command for SnapAPI
# This command applies the RBAC configuration and returns URL and token in a nice format

set -e

# Colors for nice output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}==========================================${NC}"
echo -e "${CYAN}SnapAPI RBAC Setup Command${NC}"
echo -e "${CYAN}==========================================${NC}"

# Check if oc is available
if ! command -v oc &> /dev/null; then
    echo -e "${RED}Error: oc command not found. Please ensure OpenShift CLI is installed.${NC}"
    exit 1
fi

# Check if we're logged in to OpenShift
if ! oc whoami &> /dev/null; then
    echo -e "${RED}Error: Not logged in to OpenShift. Please run 'oc login' first.${NC}"
    exit 1
fi

echo -e "${BLUE}Current user:${NC} $(oc whoami)"
echo -e "${BLUE}Current project:${NC} $(oc project -q)"
echo ""

# Create namespace if it doesn't exist
echo -e "${YELLOW}Creating namespace 'snap' if it doesn't exist...${NC}"
oc new-project snap --skip-config-write 2>/dev/null || echo "Namespace 'snap' already exists or created successfully"
echo ""

# Apply RBAC configuration
echo -e "${YELLOW}Applying RBAC configuration...${NC}"
oc apply -f snapapi-rbac.yaml
echo ""

# Wait a moment for resources to be created
sleep 2

# Create permanent token
echo -e "${YELLOW}Creating permanent token (1 year duration)...${NC}"
TOKEN=$(oc create token snapapi-serviceaccount -n snap --duration=8760h)
echo ""

# Get API server URL
echo -e "${YELLOW}Getting cluster information...${NC}"
API_SERVER=$(oc cluster-info | grep "Kubernetes control plane" | awk '{print $7}')
echo ""

# Verify permissions
echo -e "${YELLOW}Verifying service account permissions...${NC}"
echo -n "Can get pods: "
oc auth can-i get pods --as=system:serviceaccount:snap:snapapi-serviceaccount 2>/dev/null && echo -e "${GREEN}YES${NC}" || echo -e "${RED}NO${NC}"

echo -n "Can get nodes: "
oc auth can-i get nodes --as=system:serviceaccount:snap:snapapi-serviceaccount 2>/dev/null && echo -e "${GREEN}YES${NC}" || echo -e "${RED}NO${NC}"

echo -n "Can create mutatingwebhookconfigurations: "
oc auth can-i create mutatingwebhookconfigurations --as=system:serviceaccount:snap:snapapi-serviceaccount 2>/dev/null && echo -e "${GREEN}YES${NC}" || echo -e "${RED}NO${NC}"

echo -n "Can use privileged SCC: "
oc auth can-i use scc/privileged --as=system:serviceaccount:snap:snapapi-serviceaccount 2>/dev/null && echo -e "${GREEN}YES${NC}" || echo -e "${RED}NO${NC}"

echo ""
echo -e "${PURPLE}==========================================${NC}"
echo -e "${PURPLE}SnapAPI Configuration${NC}"
echo -e "${PURPLE}==========================================${NC}"
echo ""
echo -e "${GREEN}Cluster API URL:${NC}"
echo -e "${CYAN}$API_SERVER${NC}"
echo ""
echo -e "${GREEN}Service Account Token:${NC}"
echo -e "${CYAN}$TOKEN${NC}"
echo ""
echo -e "${PURPLE}==========================================${NC}"
echo -e "${PURPLE}Copy these values to your SnapUI cluster form${NC}"
echo -e "${PURPLE}==========================================${NC}"
