FROM python:3.13-slim-bookworm

LABEL org.opencontainers.image.title="GitHub Logs Collector"
LABEL org.opencontainers.image.description="Security-focused GitHub API polling collector for SIEM and log management platforms"
LABEL org.opencontainers.image.source="https://github.com/webbie003/github-logs-collector"

# Security:
# Prevent Python from creating .pyc files in the container.
ENV PYTHONDONTWRITEBYTECODE=1

# Operations:
# Send Python output immediately to Docker logging.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Security:
# Create a dedicated non-root runtime account.
RUN groupadd \
        --gid 10001 \
        collector \
    && useradd \
        --uid 10001 \
        --gid collector \
        --no-create-home \
        --shell /usr/sbin/nologin \
        collector

COPY requirements.txt .

# Security:
# Install only required dependencies and discard pip's package cache.
RUN pip install \
    --no-cache-dir \
    -r requirements.txt

COPY app/ /app/

# Security:
# Only the event log and state directories require write access.
RUN mkdir -p \
        /var/log/github \
        /var/lib/github-logs-collector \
    && chown -R \
        collector:collector \
        /var/log/github \
        /var/lib/github-logs-collector \
    && chmod 0750 \
        /var/log/github \
        /var/lib/github-logs-collector

# Security:
# Drop root privileges before starting the application.
USER 10001:10001

# No EXPOSE instruction is required.
# The collector is outbound-only and does not listen for inbound traffic.

CMD ["python", "/app/github_collector.py"]
