# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Create a non-root work dir; OpenShift will randomize the UID at runtime anyway.
WORKDIR /app

# System deps: ca-certificates, tzdata, and curl for basic diagnostics
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates tzdata curl \
 && rm -rf /var/lib/apt/lists/*

# Copy and install Python deps
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy operator code
COPY operator.py /app/

# Make sure files are readable/executable by arbitrary UIDs (OpenShift restricted SCC)
RUN chmod -R g=u /app

# Expose nothing by default; Kopf runs as a CLI process.
# If you later enable HTTP health endpoints, you can EXPOSE 8080.

# Use a non-root UID (OpenShift may override to a random UID; ensure it still works)
USER 1001

# Kopf standalone mode: relies on in-cluster permissions (ServiceAccount).
ENTRYPOINT ["kopf", "run", "--standalone", "--verbose", "--all-namespaces", "/app/operator.py"]