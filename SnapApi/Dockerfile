# First stage: Build checkpointctl
FROM golang:1.23 AS builder
RUN git clone https://github.com/checkpoint-restore/checkpointctl.git && \
    cd checkpointctl && \
    make && \
    mv checkpointctl /checkpointctl

# Final stage: Main application
FROM registry.access.redhat.com/ubi9/python-39

LABEL name="1001_1001api" \
      vendor="WeaverSoft.io" \
      maintainer="support@weaversoft.io" \
      summary="1001 API service for container checkpointing" \
      description="Handles API layer of 1001 platform. Red Hat certification compliant."



USER root

# Install system dependencies
RUN dnf install -y crit wget buildah tar gzip skopeo --allowerasing curl libselinux-utils container-selinux \
    glibc glibc-langpack-en && dnf clean all

# Set up environment
ENV LD_LIBRARY_PATH=/lib64:$LD_LIBRARY_PATH

# Install oc CLI
RUN curl -L https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/ocp/latest/openshift-client-linux.tar.gz -o oc.tar.gz \
    && tar zxvf oc.tar.gz -C /usr/local/bin \
    && rm -f oc.tar.gz


# Copy checkpointctl from builder stage
COPY --from=builder /checkpointctl /usr/local/bin/

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Set working directory
WORKDIR /app

# Copy requirements file
COPY src/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY src/. .


RUN mkdir -p /licenses 

# COPY LICENSE /licenses/

# Copy docs directory for documentation system
COPY docs /app/docs

# create user 1001
RUN useradd -r -u 669 -g 0 -m -d /home/snap -s /bin/bash snap
# Prepare for Buildah to run with non-root privileges, avoiding subuid/subgid requirements
RUN touch /etc/subgid /etc/subuid \
&& chmod g=u /etc/subgid /etc/subuid /etc/passwd \
&& echo snap:10000:65536 > /etc/subuid \    
&& echo snap:10000:65536 > /etc/subgid

RUN echo "export BUILDAH_ISOLATION=chroot" >> /home/snap/.bashrc
# Use VFS because fuse does not work
RUN echo '[storage]' > /etc/containers/storage.conf && echo 'driver = "vfs"' >> /etc/containers/storage.conf

# Create checkpoints directory with proper permissions
RUN mkdir -p /app/checkpoints && \
    chown -R 669:0 /app/checkpoints && \
    chmod -R 775 /app/checkpoints

# Copy and set up entrypoint script to fix permissions at runtime
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose the port
EXPOSE 8000

# Use entrypoint to fix permissions, then switch to snap user
ENTRYPOINT ["/docker-entrypoint.sh"]

# The container will run as `SNAP` user (via entrypoint)
# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app", "--timeout-graceful-shutdown", "0"]