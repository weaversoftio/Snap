#!/bin/bash

# Snap Development Environment Startup Script

echo "🚀 Starting Snap Development Environment..."

# Check if podman-compose is available
if ! command -v podman-compose &> /dev/null; then
    echo "❌ podman-compose not found. Please install it first."
    exit 1
fi

# Stop any existing containers
echo "🛑 Stopping existing containers..."
podman-compose -f podman-compose.dev.yml down

# Start development environment
echo "🏗️  Building and starting development containers..."
podman-compose -f podman-compose.dev.yml up --build -d

# Wait a moment for services to start
echo "⏳ Waiting for services to start..."
sleep 10

# Check service status
echo "📊 Checking service status..."
podman-compose -f podman-compose.dev.yml ps

echo ""
echo "✅ Development environment started!"
echo ""
echo "🌐 Services available at:"
echo "   • SnapUI: http://localhost:3000"
echo "   • SnapAPI: http://localhost:8000"
echo "   • SnapAPI Docs: http://localhost:8000/docs"
echo "   • SnapHook Webhook: https://localhost:8443/mutate"
echo ""
echo "📝 To view logs:"
echo "   • All services: podman-compose -f podman-compose.dev.yml logs -f"
echo "   • API only: podman-compose -f podman-compose.dev.yml logs -f snapapi"
echo "   • UI only: podman-compose -f podman-compose.dev.yml logs -f snapui"
echo ""
echo "🛑 To stop: podman-compose -f podman-compose.dev.yml down"
