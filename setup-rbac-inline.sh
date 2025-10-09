#!/bin/bash
# One-liner RBAC setup command that applies RBAC content inline and returns URL and token
# This command embeds the YAML content and applies it directly without needing external files

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

# Create namespace if it doesn't exist
echo -e "${YELLOW}Creating namespace 'snap'...${NC}"
oc new-project snap --skip-config-write 2>/dev/null || true

# Apply RBAC configuration inline
echo -e "${YELLOW}Applying RBAC configuration...${NC}"
oc apply -f - <<EOF
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: snapapi-serviceaccount
  namespace: snap
automountServiceAccountToken: true
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: snapapi-clusterrole
rules:
  # Core Kubernetes API Group - Only resources actually used by SnapAPI
  - apiGroups: [""]
    resources: 
      - "nodes"           # Used in: src/flows/checkpoint_*.py (checkpoint API requires access to nodes resource)
      - "nodes/proxy"     # Used in: src/flows/checkpoint_*.py (/api/v1/nodes/{node_name}/proxy/checkpoint/...) - requires CREATE for checkpoint API
      - "pods"            # Used in: src/routes/pod.py (kubectl get pods -A), src/flows/checkpoint_*.py (fetch_pod_info_from_k8s_api), src/classes/operator_watcher.py (delete_namespaced_pod)
      - "pods/log"        # Used in: src/flows/checkpoint_*.py (oc debug node command requires pods/log access)
      - "pods/exec"       # Used in: src/flows/checkpoint_*.py (oc debug node command may require pods/exec access)
      - "namespaces"      # Used in: src/routes/operator.py (namespace scope operations)
    verbs: ["get", "list", "watch", "create", "delete"]

  # Apps API Group - Used for ReplicaSet operations (template hash extraction)
  - apiGroups: ["apps"]
    resources: 
      - "replicasets"     # Used in: src/flows/checkpoint_container_kubelet.py (oc get replicaset for template hash)
    verbs: ["get", "list"]

  # OpenShift Security Context Constraints - Required for oc debug node operations
  - apiGroups: ["security.openshift.io"]
    resources: 
      - "securitycontextconstraints"
    verbs: ["use"]
    resourceNames: ["privileged"]  # Used in: src/flows/checkpoint_*.py (oc debug node/{node_name} -- chroot /host curl...)

  # Admission Webhook Configuration - For SnapHook webhook management
  - apiGroups: ["admissionregistration.k8s.io"]
    resources: 
      - "mutatingwebhookconfigurations"    # Used in: src/classes/snaphook.py (create_mutating_webhook_configuration)
      - "validatingwebhookconfigurations"  # Used in: src/classes/snaphook.py (webhook management operations)
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]

---
# ClusterRoleBinding to bind the service account to the cluster role
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: snapapi-clusterrolebinding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: snapapi-clusterrole
subjects:
- kind: ServiceAccount
  name: snapapi-serviceaccount
  namespace: snap
EOF

# Wait for resources to be created
sleep 2

# Create permanent token
echo -e "${YELLOW}Creating permanent token (1 year duration)...${NC}"
TOKEN=$(oc create token snapapi-serviceaccount -n snap --duration=8760h)

# Get API server URL
echo -e "${YELLOW}Getting cluster information...${NC}"
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
