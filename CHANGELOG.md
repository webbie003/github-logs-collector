# Changelog

All notable changes to `github-logs-collector` are documented here.

The format follows the general principles of Keep a Changelog.

## [Unreleased]

No unreleased changes currently documented.

---

## [0.2.1] - 2026-08-13

### Added

- Added Docker health monitoring based on the most recent successfully completed GitHub polling cycle.
- Added `app/healthcheck.py`.
- Added configurable `HEALTH_MAX_AGE`.
- Added persistent `last_successful_poll` state used by the Docker health check.
- Added `docs/GITHUB_SECURITY_SETUP.md` with guidance for configuring GitHub repository security features.
- Added guidance for existing repositories and future-repository security defaults.
- Added GitHub security API troubleshooting guidance for HTTP `401`, `403`, and `404` responses.
- Added release security validation guidance.
- Added runtime vulnerability-scanning guidance using Trivy.

### Changed

- Migrated the runtime container from Debian slim to Alpine Linux.
- Runtime base is now `python:3.13.15-alpine3.24`.
- Updated container account creation for Alpine Linux.
- Updated Docker image version to `0.2.1`.
- Updated Docker Compose defaults to `0.2.1`.
- Updated documentation for the Alpine runtime.
- Updated documentation for health monitoring.
- Updated GitHub repository security configuration guidance.
- Updated Docker security guidance.
- Updated Wazuh integration documentation for `0.2.1`.
- Updated collector version/User-Agent references to `0.2.1`.
- Clarified that repository discovery and repository security-feature availability are separate conditions.

### Security

- Removed unnecessary runtime Python packaging tooling.
- `pip` is now used only during image construction and removed from the final runtime image.
- Removed scanner-visible vulnerable libraries that were vendored by pip but not required by the collector.
- Reduced the operating-system package footprint by migrating from Debian slim to Alpine Linux.
- Maintained dedicated non-root execution as UID/GID `10001:10001`.
- Maintained read-only root filesystem support.
- Maintained `no-new-privileges`.
- Maintained the ability to drop all Linux capabilities.
- Maintained outbound-only networking with no published collector ports.
- Maintained TLS certificate verification for GitHub API requests.
- Added health monitoring that detects stalled or repeatedly unsuccessful polling.
- Documented least-privilege GitHub token configuration.
- Documented that runtime dependency changes must be made through image rebuilds rather than interactive package installation.

### Vulnerability Remediation

The previous Debian-based runtime image produced multiple operating-system and Python packaging-tool vulnerability findings during Trivy testing.

The `0.2.1` runtime was migrated to Alpine Linux and unnecessary Python packaging tooling was removed.

A final release-candidate scan using Trivy reported:

```text
CRITICAL: 0
HIGH:     0
```

This result reflects the vulnerability database available at scan time and is not a guarantee against future vulnerability discoveries.

### Reliability

- Docker health status now represents successful collector progress rather than only process existence.
- Temporary repository-specific security API failures remain isolated from other repositories.
- Unavailable security APIs do not terminate the entire polling process.
- Persistent deduplication state remains available across container recreation.

## [0.2.0] - 2026-08-12

### Added

- Initial GitHub REST API polling architecture.
- Authenticated GitHub account event collection.
- Repository discovery.
- Dependabot alert collection.
- Code scanning alert collection.
- Secret scanning alert collection.
- Structured JSONL event output.
- Original GitHub payload retention.
- Normalised event metadata.
- SQLite event deduplication.
- Persistent collector state.
- GitHub API rate-limit handling.
- Configurable polling intervals.
- Configurable request timeouts.
- Bounded API pagination.
- Graceful shutdown handling.
- Docker deployment support.
- Wazuh integration examples.
- SIEM-neutral architecture.
- Security
- Non-root container execution.
- No inbound collector listener.
- No published Docker ports required.
- Read-only container root filesystem support.
- no-new-privileges support.
- All Linux capabilities can be dropped.
- Runtime resource limits.
- Runtime GitHub token configuration.
- TLS certificate verification.

If your actual `0.2.0` changelog on GitHub contains more detail, preserve that exact existing section instead of replacing it with my condensed historical entry.

---

# 5. Full Docker Compose example

`examples/docker-compose/docker-compose.yml`:

```yaml
services:
  github-logs-collector:
    image: ghcr.io/webbie003/github-logs-collector:${COLLECTOR_VERSION:-0.2.1}
    container_name: github-logs-collector

    restart: unless-stopped
    init: true

    env_file:
      - .env

    environment:
      # Collector polling configuration.
      POLL_INTERVAL: ${POLL_INTERVAL:-300}
      REQUEST_TIMEOUT: ${REQUEST_TIMEOUT:-20}
      MAX_PAGES: ${MAX_PAGES:-10}

      # Collector operational logging.
      LOG_LEVEL: ${LOG_LEVEL:-INFO}

      # Persistent event output.
      GITHUB_LOG_FILE: ${GITHUB_LOG_FILE:-/var/log/github/events.jsonl}

      # Persistent SQLite deduplication state.
      STATE_DATABASE: ${STATE_DATABASE:-/var/lib/github-logs-collector/state.db}

      # Reliability:
      # Updated after every successfully completed polling cycle.
      LAST_SUCCESS_FILE: ${LAST_SUCCESS_FILE:-/var/lib/github-logs-collector/last_successful_poll}

      # Reliability:
      # Maximum acceptable age of the last successful poll.
      #
      # Default:
      #   POLL_INTERVAL=300
      #   HEALTH_MAX_AGE=900
      #
      # This allows approximately three missed polling intervals before
      # Docker reports the collector as unhealthy.
      HEALTH_MAX_AGE: ${HEALTH_MAX_AGE:-900}

      GITHUB_API_URL: ${GITHUB_API_URL:-https://api.github.com}

    volumes:
      # Persistent JSONL event output.
      - github_logs:/var/log/github

      # Persistent SQLite and health state.
      - github_state:/var/lib/github-logs-collector

    # Reliability:
    # Health is based on actual successful GitHub polling rather than
    # simply confirming that the Python process still exists.
    healthcheck:
      test:
        [
          "CMD",
          "python",
          "/app/healthcheck.py"
        ]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 5m

    # Security:
    # Prevent privilege elevation.
    security_opt:
      - no-new-privileges:true

    # Security:
    # The collector requires no Linux capabilities.
    cap_drop:
      - ALL

    # Security:
    # Application and Python runtime should remain immutable.
    read_only: true

    # Security:
    # Provide temporary storage without making the root filesystem writable.
    tmpfs:
      - /tmp:size=16M,mode=1777

    # Security / availability:
    # Limit resource consumption if the process misbehaves.
    pids_limit: 50
    mem_limit: 128m
    cpus: 0.25

    stop_grace_period: 30s

    # Operations:
    # Bound Docker's own stdout/stderr log growth.
    logging:
      driver: json-file
      options:
        max-size: "20m"
        max-file: "5"

    # Security:
    # No interactive shell is required during normal operation.
    stdin_open: false
    tty: false

    # No ports are published.
    #
    # GitHub Logs Collector performs outbound HTTPS polling only.

    # Optional:
    # A direct SIEM network is normally unnecessary when the SIEM reads the
    # github_logs volume. Attach an external network only when another
    # integration explicitly requires direct container-to-container traffic.
    #
    # networks:
    #   - <SIEM_NETWORK>

volumes:
  github_logs:
  github_state:

# Optional external SIEM network.
#
# networks:
#   <SIEM_NETWORK>:
#     external: true
