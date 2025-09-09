# First stage: Build checkpointctl
FROM golang:1.23 AS builder
RUN git clone https://github.com/checkpoint-restore/checkpointctl.git && \
    cd checkpointctl && \
    make && \
    mv checkpointctl /checkpointctl

# Final stage: Main application
FROM registry.access.redhat.com/ubi9/python-39

USER root

# Install system dependencies
RUN dnf install -y wget buildah tar gzip skopeo --allowerasing curl libselinux-utils container-selinux \
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

# Expose the port
EXPOSE 8000

# Run the application
CMD ["/bin/bash", "/app/run-snap.sh"]