# SnapAPI RBAC Setup Command

## Overview

The SnapUI now includes a "Copy RBAC Setup Command" button in the "Add Cluster" form that provides a one-line command to set up RBAC permissions for SnapAPI.

## How to Use

1. **Open SnapUI** and navigate to the "Add Cluster" form
2. **Click "Copy RBAC Setup Command"** button (with copy icon)
3. **Paste the command** into your terminal where you have `oc` CLI access
4. **Run the command** - it will:
   - Create the `snap` namespace
   - Apply all required RBAC permissions
   - Generate a service account token
   - Display the cluster API URL and token in a nice format
5. **Copy the displayed values** to your SnapUI cluster form

## What the Command Does

The command applies the complete RBAC configuration inline, including:

- **Service Account**: `snapapi-serviceaccount` in `snap` namespace
- **Cluster Role**: `snapapi-clusterrole` with all required permissions
- **Cluster Role Binding**: Links the service account to the cluster role
- **Token Generation**: Creates a 1-year duration token
- **Permission Verification**: Checks that all permissions are working

## Required Permissions

The RBAC setup includes permissions for:

- **Nodes**: Access to node information and checkpoint API
- **Pods**: List, get, delete pods (including debug pods)
- **Webhooks**: Manage mutating and validating webhook configurations
- **SCC**: Use privileged Security Context Constraints for debug operations
- **ReplicaSets**: Extract template hashes for container identification

## Command Output

After running the command, you'll see output like:

```
==========================================
SnapAPI Configuration
==========================================

Cluster API URL:
https://api.your-cluster.com:6443

Service Account Token:
eyJhbGciOiJSUzI1NiIsImtpZCI6Ik...

==========================================
Copy these values to your SnapUI cluster form
==========================================
```

## Prerequisites

- OpenShift CLI (`oc`) installed and configured
- Logged in to your OpenShift cluster (`oc login`)
- Admin privileges to create cluster roles and bindings

## Browser Compatibility

The copy functionality works in modern browsers with clipboard API support. For older browsers, it falls back to the legacy `document.execCommand('copy')` method.
