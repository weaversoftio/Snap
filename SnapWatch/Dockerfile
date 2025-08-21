# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates tzdata curl \
 && rm -rf /var/lib/apt/lists/*


COPY requirements.txt /app/

RUN pip install --no-cache-dir -r requirements.txt

COPY operator.py /app/

RUN chmod -R g=u /app

USER 1001

ENTRYPOINT ["kopf", "run", "--standalone", "--all-namespaces", "/app/operator.py"]