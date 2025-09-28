---
layout: default
title: SNAP Documentation
description: Comprehensive documentation for SNAP container checkpointing platform
---

<!-- Updated: Testing GitHub Pages deployment from v1.2 branch -->

# Welcome to SNAP Documentation

**SNAP** is an enterprise-grade container checkpointing and state management platform that revolutionizes how organizations handle container lifecycle management, disaster recovery, and application migration in Openshift environments.

## 🚀 Quick Start

Get up and running with SNAP in minutes:

1. **[Installation Guide](installation.md)** - Complete setup instructions
2. **[Quick Start Tutorial](quick-start.md)** - Create your first checkpoint
3. **[API Reference](api-endpoints.md)** - Complete API documentation

## 📚 Documentation Sections

### Getting Started
- **[Installation Guide](installation.md)** - System requirements and installation methods
- **[Quick Start](quick-start.md)** - Step-by-step tutorial to create your first checkpoint
- **[Configuration](configuration.md)** - System configuration and setup

### User Guides
- **[Cluster Management](cluster-management.md)** - Managing Openshift/Kubernetes clusters
- **[Checkpointing](checkpointing.md)** - Creating and managing checkpoints
- **[Registry Integration](registry-integration.md)** - Container registry setup and management
- **[Automation](automation.md)** - Automated workflows and webhooks

### API Reference
- **[API Overview](api-overview.md)** - REST API introduction and authentication
- **[API Endpoints](api-endpoints.md)** - Complete endpoint reference
- **[Webhooks](webhooks.md)** - Webhook configuration and usage

### Advanced Topics
- **[SnapWatcher Operator](snapwatcher.md)** - Operator configuration and management
- **[SnapHook System](snaphook.md)** - Webhook automation system
- **[Security](security.md)** - Security best practices and configuration
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions

## 🎯 Key Features

- **Live Container Checkpointing**: Capture complete runtime state without downtime
- **Checkpoint-to-Image Conversion**: Transform checkpoints into portable container images
- **Cross-Environment Restoration**: Restore states across different clusters
- **Multi-Cluster Management**: Centralized management across multiple clusters
- **Enterprise Security**: RBAC, audit logging, SSL/TLS encryption
- **Automated Workflows**: SnapHook webhooks and SnapWatcher operator integration

## 🏗️ Architecture

SNAP consists of several key components:

- **SnapAPI**: FastAPI-based backend service with REST API endpoints
- **SnapUI**: React-based web interface for management and monitoring
- **SnapWatcher**: Operator that runs inside SnapAPI for container monitoring
- **SnapHook**: Webhook system for automation and event-driven operations
- **Cluster Monitor DaemonSet**: User-deployed component for cluster monitoring

## 📖 Use Cases

### Disaster Recovery
- Instant application state backup and recovery
- Cross-region disaster recovery with minimal RTO/RPO
- Application state preservation during infrastructure failures

### Application Migration
- Seamless migration between Openshift clusters
- Legacy application containerization with state preservation
- Blue-green deployments with instant rollback capabilities

### Development & Testing
- Development environment state capture and sharing
- Testing with real production-like states
- Rapid environment provisioning and teardown

## 🔧 Installation Methods

### Docker Compose (Recommended)
```bash
git clone https://github.com/weaversoftio/Snap.git
cd Snap
docker-compose up -d
```

### Kubernetes Deployment
```bash
kubectl create namespace snap
kubectl apply -f k8s/
```

### Helm Chart
```bash
helm repo add snap https://weaversoftio.github.io/Snap/charts
helm install snap snap/snap
```

## 🚀 Getting Started

1. **Install SNAP** following the [Installation Guide](installation.md)
2. **Configure your first cluster** using the [Quick Start](quick-start.md)
3. **Create your first checkpoint** and convert it to an image
4. **Set up automation** with SnapHook webhooks
5. **Explore advanced features** in the user guides

## 📞 Support

- **Documentation**: Browse the comprehensive guides above
- **Issues**: [GitHub Issues](https://github.com/weaversoftio/Snap/issues)
- **Support**: support@weaversoft.io
- **Community**: Join our community discussions

## 🤝 Contributing

We welcome contributions to improve SNAP! Please see our [Contributing Guide](contributing.md) for details on how to:

- Report issues and suggest improvements
- Submit code changes and documentation updates
- Add new features and capabilities

---

**Ready to get started?** Begin with our [Installation Guide](installation.md) or jump straight to the [Quick Start Tutorial](quick-start.md)!
