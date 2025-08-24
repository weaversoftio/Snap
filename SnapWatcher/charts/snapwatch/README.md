# SnapWatcher Helm Chart

This Helm chart deploys SnapWatcher, a Kubernetes operator for automatic pod checkpointing.

## Description

SnapWatcher is a Kubernetes operator that monitors pods with specific labels and automatically triggers checkpointing when they reach a running state. It integrates with the SnapAPI to perform container checkpointing operations.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- Container runtime with checkpointing support (e.g., CRI-O with runc 1.2+)

## Installing the Chart

To install the chart with the release name `snapwatcher`:

```bash
helm install snapwatcher ./snapwatcher
```

The command deploys SnapWatcher on the Kubernetes cluster in the default configuration. The [Parameters](#parameters) section lists the parameters that can be configured during installation.

## Uninstalling the Chart

To uninstall/delete the `snapwatcher` deployment:

```bash
helm delete snapwatcher
```

The command removes all the Kubernetes components associated with the chart and deletes the release.

## Parameters

### Global parameters

| Name                      | Description                                     | Value |
| ------------------------- | ----------------------------------------------- | ----- |
| `nameOverride`            | String to partially override snapwatcher.fullname | `""`  |
| `fullnameOverride`        | String to fully override snapwatcher.fullname     | `""`  |

### Image parameters

| Name                | Description                                          | Value           |
| ------------------- | ---------------------------------------------------- | --------------- |
| `image.repository`  | SnapWatcher image repository                           | `snapwatcher`     |
| `image.tag`         | SnapWatcher image tag (immutable tags are recommended) | `""`            |
| `image.pullPolicy`  | SnapWatcher image pull policy                          | `IfNotPresent`  |
| `imagePullSecrets`  | SnapWatcher image pull secrets                         | `[{"name": "nexus-registry-secret"}]` |

### Deployment parameters

| Name                                    | Description                                               | Value   |
| --------------------------------------- | --------------------------------------------------------- | ------- |
| `replicaCount`                          | Number of SnapWatcher replicas to deploy                    | `1`     |
| `podAnnotations`                        | Annotations for SnapWatcher pods                            | `{}`    |
| `podSecurityContext`                    | Set SnapWatcher pod's Security Context                      | `{}`    |
| `securityContext`                       | Set SnapWatcher container's Security Context                | `{}`    |

### Service Account parameters

| Name                         | Description                                                | Value  |
| ---------------------------- | ---------------------------------------------------------- | ------ |
| `serviceAccount.create`      | Specifies whether a ServiceAccount should be created       | `true` |
| `serviceAccount.annotations` | Additional Service Account annotations                     | `{}`   |
| `serviceAccount.name`        | The name of the ServiceAccount to use                      | `""`   |

### RBAC parameters

| Name          | Description                                          | Value  |
| ------------- | ---------------------------------------------------- | ------ |
| `rbac.create` | Specifies whether RBAC resources should be created   | `true` |

### Namespace parameters

| Name               | Description                                    | Value   |
| ------------------ | ---------------------------------------------- | ------- |
| `namespace.create` | Specifies whether to create the namespace      | `true`  |
| `namespace.name`   | The name of the namespace to use               | `"snap"` |

### Resource parameters

| Name                        | Description                                     | Value     |
| --------------------------- | ----------------------------------------------- | --------- |
| `resources.limits.cpu`      | The CPU limit for the SnapWatcher container       | `200m`    |
| `resources.limits.memory`   | The memory limit for the SnapWatcher container    | `256Mi`   |
| `resources.requests.cpu`    | The requested CPU for the SnapWatcher container   | `50m`     |
| `resources.requests.memory` | The requested memory for the SnapWatcher container| `64Mi`    |

### Autoscaling parameters

| Name                                            | Description                                                                                                          | Value   |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ------- |
| `autoscaling.enabled`                           | Enable Horizontal Pod Autoscaler (HPA)                                                                               | `false` |
| `autoscaling.minReplicas`                       | Minimum number of SnapWatcher replicas                                                                                 | `1`     |
| `autoscaling.maxReplicas`                       | Maximum number of SnapWatcher replicas                                                                                 | `100`   |
| `autoscaling.targetCPUUtilizationPercentage`    | Target CPU utilization percentage                                                                                    | `80`    |
| `autoscaling.targetMemoryUtilizationPercentage` | Target Memory utilization percentage                                                                                 | `""`    |

### SnapWatcher specific parameters

| Name                                          | Description                                    | Value                              |
| --------------------------------------------- | ---------------------------------------------- | ---------------------------------- |
| `snapwatcher.operator.logLevel`                | Log level for the operator                      | `"INFO"`                           |
| `snapwatcher.operator.allNamespaces`           | Whether to run in all namespaces                | `true`                             |
| `snapwatcher.operator.standalone`              | Standalone mode                                 | `true`                             |
| `snapwatcher.checkpoint.snapBackApiUrl`        | SnapAPI endpoint for checkpoint requests        | `"http://snap-back-api"`           |
| `snapwatcher.checkpoint.kubeApiAddress`        | Kubernetes API server address                   | `"https://kubernetes.default.svc"` |
| `snapwatcher.checkpoint.requestTimeout`        | Request timeout in seconds                      | `5`                                |

## Configuration and installation details

### Pod Labels

SnapWatcher monitors pods with the following labels:
- `snap.weaversoft.io/snap: "true"`
- `snap.weaversoft.io/mutated: "false"`

### Checkpointing Process

When a pod with the required labels reaches the Running state and all containers are ready, SnapWatcher will:

1. Extract pod metadata (name, namespace, node, container name)
2. Resolve the deployment owner from ReplicaSet references
3. Send a checkpoint request to the configured SnapAPI endpoint

### Environment Variables

The following environment variables are automatically configured:

- `SNAPWATCH_LOG_LEVEL`: Controls the logging level
- `SNAPBACK_API_URL`: URL of the SnapAPI service
- `KUBE_API_ADDRESS`: Kubernetes API server address
- `REQUEST_TIMEOUT`: Timeout for checkpoint requests

## Troubleshooting

### Common Issues

1. **RBAC Permissions**: Ensure the service account has the necessary permissions to watch pods, events, and access ReplicaSets/Deployments.

2. **Image Pull Issues**: Verify that the image pull secrets are correctly configured and the image repository is accessible.

3. **Checkpoint Failures**: Check the SnapWatcher logs for connection issues with the SnapAPI endpoint.

### Viewing Logs

```bash
kubectl logs -n snap deployment/snapwatcher
```

### Checking RBAC

```bash
kubectl auth can-i get pods --as=system:serviceaccount:snap:snapwatcher
kubectl auth can-i list pods --as=system:serviceaccount:snap:snapwatcher
kubectl auth can-i watch pods --as=system:serviceaccount:snap:snapwatcher
