FROM python:3.13.15-alpine3.24

LABEL org.opencontainers.image.title="GitHub Logs Collector"
LABEL org.opencontainers.image.description="Security-focused GitHub API polling collector for SIEM and log management platforms"
LABEL org.opencontainers.image.source="https://github.com/webbie003/github-logs-collector"
LABEL org.opencontainers.image.version="0.2.1"

# Security:
# Prevent Python from writing bytecode files into the container filesystem.
ENV PYTHONDONTWRITEBYTECODE=1

# Operations:
# Send Python output directly to Docker logging without buffering.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Security:
# Run the collector as a dedicated non-root user.
RUN addgroup \
      -g 10001 \
      -S collector \
    && adduser \
      -u 10001 \
      -S \
      -D \
      -H \
      -G collector \
      collector

COPY requirements.txt .

# Security:
# Install only required runtime dependencies.
#
# pip is needed only while constructing the image. It and its vendored
# libraries are removed after installation to reduce the final runtime
# attack surface.
RUN python -m pip install \
      --no-cache-dir \
      -r requirements.txt \
    && python -m pip uninstall \
      --yes \
      pip

COPY app/ /app/

# Security:
# Limit persistent write access to the collector's log and state paths.
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

USER 10001:10001

CMD ["python", "/app/github_collector.py"]
