# SNAP - Container State Management Platform

**"SNAP it, Save it, Start again."**

SNAP is an enterprise-grade container checkpointing and state management platform that revolutionizes how organizations handle container lifecycle management, disaster recovery, and application migration in Openshift environments.

## Overview

SNAP enables organizations to capture the complete runtime state of running containers, convert them into portable images, and restore them across different environments. This breakthrough technology transforms containerized applications from stateless to stateful, enabling unprecedented flexibility in application management.

## Key Features

- **Live Container Checkpointing**: Capture complete runtime state without downtime using CRIU
- **Checkpoint-to-Image Conversion**: Transform checkpoints into portable container images
- **Cross-Environment Restoration**: Restore states across different Kubernetes/Openshift clusters
- **Multi-Cluster Management**: Centralized management across multiple clusters
- **Enterprise Security**: RBAC, audit logging, SSL/TLS encryption
- **Automated Workflows**: SnapHook webhooks and SnapWatcher operator integration
- **Real-time Monitoring**: WebSocket-based progress tracking and health monitoring

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   SnapUI        │    │   SnapAPI       │    │   SnapWatcher   │
│   (React)       │◄──►│   (FastAPI)     │◄──►│  (Operator      │
│   Port: 3000    │    │   Port: 8000    │    │  Inside SnapAPI)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Browser   │    │   Container     │    │   Kubernetes    │
│   Management    │    │   Registry      │    │   Clusters      │
│   Interface     │    │   (Nexus, etc.) │    │   (Openshift)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       ▲
                                │                       │
                                └───────────────────────┘
```

## 📚 Documentation

### Comprehensive Guides
- **[📖 Complete Documentation](https://weaversoftio.github.io/Snap/)** - Full documentation site
- **[🚀 Quick Start Guide](https://weaversoftio.github.io/Snap/quick-start)** - Get up and running in minutes
- **[⚙️ Installation Guide](https://weaversoftio.github.io/Snap/installation)** - Detailed setup instructions
- **[🔧 API Reference](https://weaversoftio.github.io/Snap/api-endpoints)** - Complete API documentation

### Key Documentation Sections
- **Getting Started**: Installation, configuration, and first steps
- **User Guides**: Cluster management, checkpointing, registry integration
- **API Reference**: REST endpoints, authentication, and examples
- **Advanced Topics**: SnapWatcher operator, SnapHook system, security
- **Troubleshooting**: Common issues and solutions

### Interactive Resources
- **[🎯 Live Demo](https://weaversoftio.github.io/Snap/)** - Try SNAP online
- **[📋 API Explorer](https://weaversoftio.github.io/Snap/api-endpoints)** - Interactive API testing
- **[💡 Examples](https://weaversoftio.github.io/Snap/quick-start)** - Real-world use cases

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Access to Openshift/Kubernetes cluster
- Registry credentials (Nexus, Harbor, etc.)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/weaversoftio/Snap.git
   cd Snap
   ```

2. **Start SNAP services**
   ```bash
   docker-compose up -d
   ```

3. **Access the web interface**
   - Open browser to `http://localhost:3000`
   - Login with default credentials: `admin/admin`

4. **Configure your first cluster**
   - Navigate to **Configuration > Registry** and add your registry
   - Go to **Configuration > Clusters** and add your Openshift cluster
   - Deploy **SnapWatcher DaemonSet** using the provided YAML file
   - Start **SnapWatcher** operator and **SnapHook** webhooks

### Configuration Steps

1. **Registry Configuration**
   - Add registry details (URL, credentials)
   - Test connectivity

2. **Cluster Configuration**
   - Add Openshift cluster details
   - Upload kubeconfig or enter authentication token
   - Select configured registry

3. **Deploy Cluster Monitor DaemonSet**
   ```bash
   # Deploy the cluster monitoring DaemonSet to your cluster
   kubectl apply -f SnapApi/snap-cluster-monitor-daemonset.yaml
   ```

4. **Start Components**
   - **SnapWatcher Operator**: Start the operator inside SnapAPI to monitor containers
   - **SnapHook**: Create webhook endpoints for automation

## API Documentation

The SNAP API provides comprehensive REST endpoints for:

- **Checkpointing**: `/checkpoint/*` - Create, download, and manage checkpoints
- **Clusters**: `/cluster/*` - Manage cluster configurations and operations
- **Registry**: `/registry/*` - Handle registry authentication and image operations
- **Automation**: `/automation/*` - Automated workflows and triggers
- **Configuration**: `/config/*` - System and user configurations
- **Webhooks**: `/webhooks/*` - Webhook management and event handling

Access the interactive API documentation at `http://localhost:8000/docs`

## Use Cases

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


## Components

### SnapAPI
- FastAPI-based backend service
- RESTful API endpoints
- Kubernetes operator integration
- WebSocket support for real-time updates

### SnapUI
- React-based web interface
- Modern, responsive design
- Real-time dashboard and monitoring
- User-friendly configuration management

### SnapWatcher
- **Operator**: Runs inside SnapAPI, monitors containers and performs checkpointing
- Automatic checkpointing capabilities
- Real-time container monitoring
- Event-driven checkpoint operations

### SnapHook
- Webhook system for automation
- Event-driven checkpoint operations
- CI/CD pipeline integration
- Custom workflow triggers

### Cluster Monitor DaemonSet
- User-deployed Kubernetes DaemonSet for cluster monitoring
- Real-time cluster health monitoring
- Node-level configuration management
- Cluster status reporting

## Security

- **Authentication**: Token-based authentication system
- **Authorization**: Role-based access control (RBAC)
- **Encryption**: SSL/TLS for all communications
- **Audit Logging**: Comprehensive logging and audit trails
- **Compliance**: SOC 2, GDPR, and enterprise compliance features

## Development

### Local Development Setup

1. **Clone and setup**
   ```bash
   git clone https://github.com/weaversoftio/Snap.git
   cd Snap
   ```

2. **Start development environment**
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

3. **Access services**
   - API: `http://localhost:8000`
   - UI: `http://localhost:3000`
   - API Docs: `http://localhost:8000/docs`

### Project Structure


```
Snap/
├── SnapApi/                 # Backend API service
│   ├── src/
│   │   ├── app.py          # FastAPI application
│   │   ├── routes/         # API route handlers
│   │   ├── classes/        # Data models and utilities
│   │   ├── flows/          # Business logic flows
│   │   └── middleware/     # Authentication and middleware
│   ├── snap-cluster-monitor-daemonset.yaml  # Cluster monitoring DaemonSet
│   ├── Dockerfile
│   └── docker-compose.yml
├── SnapUi/                 # Frontend React application
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── features/       # Feature modules
│   │   └── api/           # API client
│   ├── Dockerfile
│   └── package.json
├── Demo/                   # Demo configurations and examples
├── docker-compose.yaml     # Production deployment
└── docker-compose.dev.yml  # Development deployment
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📖 Documentation & Resources

### 📚 Complete Documentation
Visit our comprehensive documentation site for detailed guides, tutorials, and API reference:

**🌐 [https://weaversoftio.github.io/Snap/](https://weaversoftio.github.io/Snap/)**

### 📋 Quick Links
- **[🚀 Quick Start](https://weaversoftio.github.io/Snap/quick-start)** - Get started in 5 minutes
- **[⚙️ Installation](https://weaversoftio.github.io/Snap/installation)** - Complete setup guide
- **[🔧 API Reference](https://weaversoftio.github.io/Snap/api-endpoints)** - All endpoints and examples
- **[🏗️ Architecture](https://weaversoftio.github.io/Snap/architecture)** - System design overview
- **[🔒 Security](https://weaversoftio.github.io/Snap/security)** - Security best practices
- **[🛠️ Troubleshooting](https://weaversoftio.github.io/Snap/troubleshooting)** - Common issues and solutions

### 🎯 Interactive Resources
- **Live Demo**: Try SNAP features online
- **API Explorer**: Test endpoints interactively
- **Code Examples**: Real-world implementation samples
- **Video Tutorials**: Step-by-step walkthroughs

## Support

- **📖 Documentation**: [Complete guides and tutorials](https://weaversoftio.github.io/Snap/)
- **🐛 Issues**: [GitHub Issues](https://github.com/weaversoftio/Snap/issues)
- **📧 Support**: support@weaversoft.io
- **💬 Community**: Join our community discussions

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- CRIU (Checkpoint/Restore in Userspace) for container checkpointing technology
- Kubernetes community for container orchestration platform
- Openshift community for enterprise Kubernetes distribution

