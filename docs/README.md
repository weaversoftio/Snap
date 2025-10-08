# SNAP Documentation Site

This directory contains the Jekyll-based documentation site for SNAP.

## Theme: Custom Minima with Sidebar

The documentation now uses a **customized Minima theme** with a **left sidebar navigation**, which provides:
- **Left sidebar navigation** instead of top navbar
- **Organized navigation sections** with clear categorization
- **Mobile-responsive design** with collapsible sidebar
- **Custom SNAP branding** and styling
- **Professional appearance** with modern typography

## Navigation Structure

The sidebar navigation is defined in `_layouts/default.html` and organized into logical sections:

- **Getting Started**: Quick Start, Installation, Configuration
- **User Guides**: Cluster Management, Checkpointing, Registry, Automation
- **API Reference**: API Overview, Endpoints, Authentication
- **Security & Operations**: Security, RBAC Setup, Troubleshooting
- **Additional Resources**: FAQ, Add Cluster Guide, Migration Guide

## Local Development

To run the documentation site locally:

```bash
cd docs
bundle install
bundle exec jekyll serve
```

The site will be available at `http://localhost:4000`

## Deployment

The site is automatically deployed to GitHub Pages when changes are pushed to the main branch.

## Configuration

- `_config.yml`: Main Jekyll configuration
- `_layouts/default.html`: Custom layout with sidebar navigation
- `assets/css/custom.css`: Custom CSS for sidebar and styling
- `_includes/`: Custom includes and components
- `assets/`: Static assets (images, CSS, JS)