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

# Production stage
FROM nginx:alpine

# Copy built assets from build stage
COPY --from=build /app/build /usr/share/nginx/html

# Copy config.js separately and set permissions
COPY src/public/config.js /usr/share/nginx/html/config.js

# Add entrypoint script
COPY src/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Set up directories and permissions for arbitrary user IDs (OpenShift compatible)
RUN mkdir -p /var/cache/nginx/client_temp /var/cache/nginx/proxy_temp /var/cache/nginx/fastcgi_temp /var/cache/nginx/uwsgi_temp /var/cache/nginx/scgi_temp && \
    chmod -R 777 /var/cache/nginx /usr/share/nginx/html /var/log/nginx /tmp && \
    chmod 666 /usr/share/nginx/html/config.js

# Create custom nginx config for non-privileged port and OpenShift compatibility
RUN rm /etc/nginx/conf.d/default.conf
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
        root /usr/share/nginx/html; \
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
RUN cp /usr/share/nginx/html/config.js /tmp/config.js && \
    rm /usr/share/nginx/html/config.js && \
    ln -s /tmp/config.js /usr/share/nginx/html/config.js && \
    chmod 666 /tmp/config.js

# Expose port 8080
EXPOSE 8080

# Don't specify USER - let OpenShift assign arbitrary user ID

# Change the CMD to use our entrypoint script
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
