#!/bin/bash
# One-liner RBAC setup command for SnapAPI
# Usage: curl -s https://raw.githubusercontent.com/weaversoftio/Snap/main/setup-rbac-oneliner.sh | bash
# Or: wget -qO- https://raw.githubusercontent.com/weaversoftio/Snap/main/setup-rbac-oneliner.sh | bash

set -e

# Colors for output
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; PURPLE='\033[0;35m'; CYAN='\033[0;36m'; NC='\033[0m'

echo -e "${CYAN}==========================================${NC}"
echo -e "${CYAN}SnapAPI RBAC Setup${NC}"
echo -e "${CYAN}==========================================${NC}"

# Check prerequisites
if ! command -v oc &> /dev/null; then
    echo -e "${RED}Error: oc command not found. Please install OpenShift CLI.${NC}"
    exit 1
fi

if ! oc whoami &> /dev/null; then
    echo -e "${RED}Error: Not logged in to OpenShift. Please run 'oc login' first.${NC}"
    exit 1
fi

echo -e "${BLUE}User:${NC} $(oc whoami) | ${BLUE}Project:${NC} $(oc project -q)"

# Setup RBAC
echo -e "${YELLOW}Setting up RBAC...${NC}"
oc new-project snap --skip-config-write 2>/dev/null || true
oc apply -f snapapi-rbac.yaml
sleep 2
TOKEN=$(oc create token snapapi-serviceaccount -n snap --duration=8760h)
API_SERVER=$(oc cluster-info | grep "Kubernetes control plane" | awk '{print $7}')

# Verify permissions
echo -e "${YELLOW}Verifying permissions...${NC}"
oc auth can-i get pods --as=system:serviceaccount:snap:snapapi-serviceaccount 2>/dev/null && echo -e "Pods: ${GREEN}✓${NC}" || echo -e "Pods: ${RED}✗${NC}"
oc auth can-i get nodes --as=system:serviceaccount:snap:snapapi-serviceaccount 2>/dev/null && echo -e "Nodes: ${GREEN}✓${NC}" || echo -e "Nodes: ${RED}✗${NC}"
oc auth can-i create mutatingwebhookconfigurations --as=system:serviceaccount:snap:snapapi-serviceaccount 2>/dev/null && echo -e "Webhooks: ${GREEN}✓${NC}" || echo -e "Webhooks: ${RED}✗${NC}"
oc auth can-i use scc/privileged --as=system:serviceaccount:snap:snapapi-serviceaccount 2>/dev/null && echo -e "SCC: ${GREEN}✓${NC}" || echo -e "SCC: ${RED}✗${NC}"

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
