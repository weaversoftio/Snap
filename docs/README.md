# SNAP Documentation Site

This directory contains the Jekyll-based documentation site for SNAP.

## Theme: Just the Docs

The documentation now uses the **Just the Docs** Jekyll theme, which provides:
- **Left sidebar navigation** instead of top navbar
- **Collapsible navigation** with foldable sections
- **Built-in search functionality**
- **Mobile-responsive design**
- **Clean, professional appearance**

## Navigation Structure

The sidebar navigation is defined in `_data/navigation.yml` and organized into logical sections:

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
- `_data/navigation.yml`: Sidebar navigation structure
- `_layouts/`: Custom layout templates
- `_includes/`: Custom includes and components
- `assets/`: Static assets (images, CSS, JS)