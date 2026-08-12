FROM python:3.13.15-slim-bookworm

LABEL org.opencontainers.image.title="GitHub Logs Collector"
LABEL org.opencontainers.image.description="GitHub webhook collector for SIEM and log management platforms"
LABEL org.opencontainers.image.source="https://github.com/webbie003/github-logs-collector"

# Security:
# Prevent Python from writing .pyc files into the container filesystem.
ENV PYTHONDONTWRITEBYTECODE=1

# Security / operations:
# Emit Python output immediately so logs are available to Docker/SIEM
# without buffering delays.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Security:
# Run the application under a dedicated non-root service account.
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
# Install only explicitly required dependencies and do not retain
# the pip download cache.
RUN pip install \
    --no-cache-dir \
    -r requirements.txt

COPY app/ /app/

# Security:
# Only the collector log directory is intended to be writable.
RUN mkdir -p /var/log/github \
    && chown collector:collector /var/log/github \
    && chmod 0750 /var/log/github

# Security:
# Drop root privileges before application startup.
USER 10001:10001

EXPOSE 8080

# Security:
# Gunicorn request limits reduce HTTP resource-abuse opportunities.
#
# --limit-request-line:
# Restricts HTTP request-line length.
#
# --limit-request-fields:
# Restricts the number of HTTP request headers.
#
# --limit-request-field_size:
# Restricts individual HTTP header field size.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "30", "--graceful-timeout", "30", "--keep-alive", "5", "--limit-request-line", "4094", "--limit-request-fields", "50", "--limit-request-field_size", "8190", "--access-logfile", "-", "--error-logfile", "-", "github_listener:app"]
