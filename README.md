# GitHub Logs Collector

A lightweight, security-focused GitHub webhook collector that validates
GitHub webhook signatures and writes structured JSONL events for ingestion
by SIEM and log-management platforms.

The collector is intentionally SIEM-neutral.

Example integrations are provided for platforms such as Wazuh, while the
core container has no dependency on any specific SIEM product.

## Features

- GitHub webhook ingestion
- HMAC-SHA256 webhook signature verification
- Constant-time signature comparison
- Structured JSONL output
- Full GitHub webhook payload preservation
- Normalised event metadata
- Configurable request-size limits
- Non-root container execution
- Read-only root filesystem support
- Linux capabilities can be fully dropped
- No interactive terminal requirement
- Docker health checking
- Container resource limits
- SIEM-neutral architecture
- Wazuh integration examples

## Architecture

GitHub

    |
    | HTTPS webhook
    v

Reverse proxy / TLS endpoint

    |
    | HTTP on trusted/private network
    v

github-logs-collector

    |
    | JSONL
    v

/var/log/github/events.jsonl

    |
    +----> Wazuh
    +----> Splunk
    +----> Elastic
    +----> Graylog
    +----> Fluent Bit
    +----> other log platforms

## Security Model

The collector is designed to minimise attack surface when deployed as an
internet-facing webhook receiver.

Implemented controls include:

- GitHub HMAC-SHA256 webhook authentication
- Constant-time HMAC comparison
- Maximum request-body size
- JSON-only webhook processing
- Metadata length validation
- No arbitrary HTTP-header logging
- Non-root runtime UID/GID
- Linux capabilities can be dropped with `cap_drop: ALL`
- `no-new-privileges`
- Read-only root filesystem
- Restricted writable log volume
- In-memory `/tmp`
- Process, memory and CPU limits
- No stdin or TTY
- Docker log rotation

TLS termination should be handled by a trusted reverse proxy such as nginx,
Caddy, Traefik, HAProxy, or an equivalent ingress solution.

Do not expose Flask's development server directly to the Internet.

## Requirements

- Docker
- Docker Compose v2
- A GitHub repository or organisation where webhook configuration is permitted

## Quick Start

Copy the example deployment:

    cp .env.example .env

Generate a webhook secret:

    openssl rand -hex 32

Add the generated value to:

    GITHUB_WEBHOOK_SECRET=

Start the container:

    docker compose up -d

Check health:

    docker compose ps

or:

    curl http://127.0.0.1:8080/health

Expected response:

    {"status":"healthy"}

## GitHub Webhook Configuration

Configure the GitHub webhook with:

Payload URL:

    https://YOUR_HOST/github-webhook

Content type:

    application/json

Secret:

Use the same secret configured in `GITHUB_WEBHOOK_SECRET`.

SSL verification should remain enabled.

## Output

Events are written as newline-delimited JSON:

    /var/log/github/events.jsonl

Example:

    {
      "@timestamp":"2026-08-12T03:00:00+00:00",
      "source":{
        "type":"github",
        "transport":"webhook"
      },
      "github":{
        "event":"push",
        "delivery_id":"...",
        "repository":"example/repository",
        "sender":"example-user"
      },
      "payload":{}
    }

Each event is stored on a single physical line.

## Docker Compose

A hardened example is available under:

    examples/docker-compose/

The default bind address is:

    127.0.0.1

This avoids accidentally exposing the collector to every network interface.

If direct LAN access is required, configure:

    COLLECTOR_BIND_IP=<SERVER_IP>

## SIEM Integration

### Wazuh

Example configuration is available under:

    examples/wazuh/

The Wazuh manager can monitor:

    /var/log/github/events.jsonl

using:

    <localfile>
      <log_format>json</log_format>
      <location>/var/log/github/events.jsonl</location>
    </localfile>

Where possible, mount the collector log volume read-only into the SIEM.

## Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| COLLECTOR_VERSION | Container image version | 0.1.1 |
| COLLECTOR_BIND_IP | Host interface exposed by Docker | 127.0.0.1 |
| GITHUB_WEBHOOK_SECRET | GitHub webhook authentication secret | Required |
| GITHUB_WEBHOOK_LOG | JSONL output location | /var/log/github/events.jsonl |
| MAX_CONTENT_LENGTH | Maximum HTTP body size | 5242880 |
| LOG_LEVEL | Application logging verbosity | INFO |

## Building Locally

Build:

    docker build \
      --pull \
      -t github-logs-collector:0.1.1 \
      .

Run:

    docker compose up -d

## Security

See:

    SECURITY.md

Do not report security vulnerabilities through a public GitHub issue.

## License

See:

    LICENSE
