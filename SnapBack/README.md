# SnapBack Webhook Deployment Instructions

## Overview
SnapBack is a Kubernetes mutating admission webhook that automatically modifies pod specifications during creation. It redirects container images from public registries to secure internal registries and adds mutation labels.

## Prerequisites
- Kubernetes cluster with admission controllers enabled
- `kubectl` or `oc` CLI access to the cluster
- Container registry access (e.g., `192.168.33.204:8082`)
- Helm 3.x installed
- OpenSSL for certificate generation

## Quick Deployment

### 1. Build and Push Container Image
```bash
cd SnapBack
make build
make push
```

### 2. Deploy with Helm
```bash
make install
```

### 3. Test the Webhook
```bash
oc apply -f pod.yaml
```

## Detailed Deployment Steps

### Step 1: Generate TLS Certificates
The webhook requires TLS certificates for secure communication with the Kubernetes API server.

```bash
cd SnapBack
make certs
```

This will generate:
- `tls.key` - Private key
- `tls.crt` - Certificate with proper SANs (no Common Name reliance)

### Step 2: Build Container Image
```bash
make build
```

This builds the container image with:
- Python 3.11 slim base
- FastAPI webhook server
- Proper certificate handling
- Modern lifespan event handlers

### Step 3: Push to Registry
```bash
make push
```

### Step 4: Deploy with Helm
```bash
make install
```

This command:
- Generates certificates if they don't exist
- Deploys the webhook using Helm chart
- Configures TLS certificates as Kubernetes secrets
- Sets up the MutatingWebhookConfiguration

## Configuration

### Certificate Configuration (`csr.conf`)
```ini
[req]
default_bits = 2048
prompt = no
default_md = sha256
req_extensions = req_ext
distinguished_name = dn

[dn]
O = SnapBack Webhook

[req_ext]
subjectAltName = @alt_names

[alt_names]
DNS.1 = snapback-webhook.snap.svc
DNS.2 = snapback-webhook.snap.svc.cluster.local
```

**Important**: The certificate uses only Organization (O) field and Subject Alternative Names (SANs) to comply with modern Kubernetes certificate validation requirements.

### Webhook Configuration
The webhook is configured to intercept pods with specific labels:
- `snap.weaversoft.io/snap: "true"`
- `snap.weaversoft.io/mutated: "false"`

### Image Registry Mapping
The webhook automatically replaces:
- `docker.io/library/*` → `registry.weaversoft.io/secure/*`

## Verification

### Check Webhook Pod Status
```bash
oc get pods -n snap -l app=snapback
```

### View Webhook Logs
```bash
oc logs -n snap -l app=snapback
```

### Test Pod Creation
```bash
oc apply -f pod.yaml
```

Expected behavior:
1. Pod creation request intercepted by webhook
2. Container image modified from `docker.io/library/nginx:latest` to `registry.weaversoft.io/secure/nginx:latest`
3. Label `snap.weaversoft.io/mutated` set to `"true"`
4. Pod created successfully with mutations applied

## Troubleshooting

### Certificate Issues
If you encounter certificate validation errors:

1. **Legacy Common Name Error**:
   ```
   x509: certificate relies on legacy Common Name field, use SANs instead
   ```
   Solution: Regenerate certificates with `make clean && make certs`

2. **Certificate Verification Failed**:
   - Ensure certificates have proper SANs
   - Verify service name matches certificate DNS names
   - Check that webhook configuration uses correct caBundle

### Webhook Response Issues
If webhook returns invalid response format:
- Ensure response includes `apiVersion: "admission.k8s.io/v1"` and `kind: "AdmissionReview"`
- Check webhook logs for errors

### Pod Restart Required
After certificate or code changes:
```bash
oc rollout restart deployment snapback -n snap
```

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make certs` | Generate TLS certificates |
| `make build` | Build container image |
| `make push` | Push image to registry |
| `make install` | Deploy webhook with Helm |
| `make clean` | Remove generated certificates |

## Security Considerations

1. **TLS Certificates**: Use proper SANs, avoid Common Name reliance
2. **RBAC**: Webhook has minimal required permissions
3. **Image Security**: Redirects to secure internal registry
4. **Namespace Isolation**: Deployed in dedicated `snap` namespace

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   kubectl/oc    │───▶│  Kubernetes API  │───▶│  SnapBack       │
│   apply pod     │    │     Server       │    │  Webhook        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │  Pod Created     │    │  Image Registry │
                       │  with Mutations  │    │  Redirection    │
                       └──────────────────┘    └─────────────────┘
```

## Files Structure

```
SnapBack/
├── src/
│   ├── main.py          # FastAPI application
│   ├── webhook.py       # Webhook mutation logic
│   ├── certs.py         # Certificate management
│   └── requirements.txt # Python dependencies
├── charts/snapback/     # Helm chart
├── csr.conf            # Certificate configuration
├── Dockerfile          # Container build
├── Makefile           # Build automation
└── DEPLOYMENT.md      # This file
```

## Support

For issues or questions:
1. Check webhook pod logs
2. Verify certificate configuration
3. Test with sample pod.yaml
4. Review MutatingWebhookConfiguration settings
