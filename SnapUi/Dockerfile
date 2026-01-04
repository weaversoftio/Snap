# Build stage
FROM node:20-alpine as build

# Set working directory
WORKDIR /app

# Copy package files
COPY src/package*.json ./

# Install dependencies
RUN yarn install

# Copy source code
COPY src/. .

# Build the app
RUN yarn build

# Production stage - Use Red Hat UBI with nginx
FROM registry.access.redhat.com/ubi9/nginx-122:latest

# Add required labels for Red Hat certification
LABEL name="snapui" \
      vendor="Weaversoft.io" \
      version="1.0.0" \
      release="1" \
      summary="Snap UI - Kubernetes Pod Checkpoint and Restore Web Interface" \
      description="Web interface for the Snap Kubernetes Pod Checkpoint and Restore Operator. Provides management and monitoring capabilities for pod checkpoint operations." \
      maintainer="Weaversoft.io <sales@weaversoft.io>"

# Switch to root to perform setup operations
USER root

# Update all packages to fix security vulnerabilities (CVE-2025-6965, CVE-2025-59375, CVE-2025-8176)
# This updates sqlite, expat, libtiff and other system packages to their latest patched versions
RUN dnf update -y && dnf clean all

# Create licenses directory and add license file
RUN mkdir -p /licenses
COPY LICENSE /licenses/LICENSE
RUN chmod -R 755 /licenses

# Create app directory for our React build (avoid overwriting base image files)
RUN mkdir -p /opt/app-root/src

# Copy built assets from build stage to custom directory
COPY --from=build /app/build /opt/app-root/src

# Copy config.js separately and set permissions
COPY src/public/config.js /opt/app-root/src/config.js

# Copy runtime-config template (will be used to generate runtime-config.js at startup)
COPY src/public/runtime-config.template.js /opt/app-root/src/runtime-config.template.js
COPY src/public/runtime-config.template.js /tmp/runtime-config.template.js

# Add entrypoint script
COPY src/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Set up directories and permissions for arbitrary user IDs (OpenShift compatible)
RUN mkdir -p /var/cache/nginx/client_temp /var/cache/nginx/proxy_temp /var/cache/nginx/fastcgi_temp /var/cache/nginx/uwsgi_temp /var/cache/nginx/scgi_temp && \
    chmod -R 777 /var/cache/nginx /opt/app-root/src /var/log/nginx /tmp && \
    chmod 666 /opt/app-root/src/config.js

# Create custom nginx config for non-privileged port and OpenShift compatibility
RUN rm -f /etc/nginx/conf.d/default.conf || true
RUN echo 'pid /tmp/nginx.pid; \
error_log /tmp/error.log; \
events { \
    worker_connections 1024; \
} \
http { \
    include /etc/nginx/mime.types; \
    default_type application/octet-stream; \
    access_log /tmp/access.log; \
    client_body_temp_path /tmp/client_temp; \
    proxy_temp_path /tmp/proxy_temp_path; \
    fastcgi_temp_path /tmp/fastcgi_temp; \
    uwsgi_temp_path /tmp/uwsgi_temp; \
    scgi_temp_path /tmp/scgi_temp; \
    \
    server { \
        listen 8080; \
        server_name _; \
        root /opt/app-root/src; \
        index index.html; \
        \
        # Gzip compression \
        gzip on; \
        gzip_vary on; \
        gzip_min_length 10240; \
        gzip_proxied expired no-cache no-store private auth; \
        gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml; \
        gzip_disable "MSIE [1-6]\\."; \
        \
        location / { \
            try_files $uri $uri/ /index.html; \
            expires -1; \
        } \
        \
        # Cache static assets \
        location /static/ { \
            expires 1y; \
            add_header Cache-Control "public, no-transform"; \
        } \
        \
        # Cache other assets \
        location ~* \\.(js|css|png|jpg|jpeg|gif|ico|svg)$ { \
            expires 1y; \
            add_header Cache-Control "public, no-transform"; \
        } \
    } \
}' > /etc/nginx/nginx.conf

# Create a writable copy of config.js in /tmp and symlink it
RUN cp /opt/app-root/src/config.js /tmp/config.js && \
    rm /opt/app-root/src/config.js && \
    ln -s /tmp/config.js /opt/app-root/src/config.js && \
    chmod 666 /tmp/config.js

# Expose port 8080
EXPOSE 8080

# Run as non-root user (required for Red Hat certification)
# UBI nginx images typically use UID 1001
USER 1001

# Change the CMD to use our entrypoint script
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
