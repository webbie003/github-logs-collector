# Changelog

All notable changes to `github-logs-collector` are documented here.

The format follows the general principles of [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

No unreleased changes currently documented.

---

## [0.2.3] - 2026-08-17

### Added

- Added `github.repo` as a normalized repository alias alongside `github.repository`.
- Added Wazuh-compatible `data.github.repo` population for new events.

### Changed

- Improved Wazuh dynamic rule descriptions with richer repository, actor, workflow, status and conclusion context.
- Removed `triggered_by` from primary GitHub Actions rule descriptions to reduce dashboard noise.
- Updated Wazuh documentation for the repository alias and dynamic rule descriptions.

### Compatibility

- `github.repository` remains unchanged and continues to be emitted.
- `github.repo` is an additional compatibility/dashboard field.
- Existing indexed events are not retroactively updated.

---

## [0.2.2] - 2026-08-17

### Added

- Added GitHub Actions workflow-run telemetry.
- Added workflow actor and triggering-actor attribution.
- Added branch, commit SHA, run number and run-attempt metadata for GitHub Actions.
- Added detailed job and step telemetry for failed, cancelled, timed-out and other abnormal workflow outcomes.
- Added repository security-state monitoring for:
  - visibility
  - private/public state
  - archived/unarchived state
  - default branch
- Added persistent repository security-state baselines.
- Added security-alert lifecycle monitoring.
- Added separate structured collector operational logging to `/var/log/github/collector.jsonl`.
- Added collector operational events for:
  - startup and shutdown
  - authentication success and failure
  - GitHub API communication failures
  - API timeouts
  - rate limiting
  - polling failures
  - security collector failures
  - GitHub Actions collection failures
  - SQLite failures
  - filesystem failures
  - successful polling summaries

### Changed

- Updated collector version to `0.2.2`.
- Updated collector User-Agent to `github-logs-collector/0.2.2`.
- Security-alert collection is no longer intentionally limited to open findings only.
- GitHub Actions successful workflow runs are recorded without emitting separate successful job/step events.
- Detailed Actions job/step telemetry is focused on abnormal workflow outcomes.
- Added normalised GitHub Actions fields for workflow/run attribution.
- Added collector operational fields suitable for SIEM monitoring.
- Updated recommended GitHub fine-grained token permissions to include `Actions: Read-only`.
- Updated Docker Compose examples to include the new v0.2.2 collector configuration.
- Updated Wazuh examples to ingest both GitHub event and collector operational streams.
- Updated documentation for repository security-state monitoring.
- Updated documentation for the second JSONL output stream.

### Removed

- Removed Docker Hub API telemetry from the planned v0.2.2 feature set.
- Removed security-state monitoring for stars, watchers, fork counters, open-issue counters and other popularity/analytics metrics.
- Removed repository traffic/download analytics from the v0.2.2 scope.
- Raw GitHub Actions console-log collection is not included.

### Security

- Collector operational failures can now be independently ingested and alerted on by SIEM platforms.
- Repository visibility, default-branch and archive-state changes can now be detected.
- Failed or abnormal CI/CD workflows can now be surfaced to SIEM monitoring.
- Workflow actor and triggering-actor attribution improve investigation context.
- Security-alert lifecycle changes can now be detected where exposed by the GitHub API.
- No Docker Hub credentials or API integration were introduced.
- Raw GitHub Actions console logs are not downloaded.
- Existing outbound-only, non-root and least-privilege design is maintained.

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

---

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

### Security

- Non-root container execution.
- No inbound collector listener.
- No published Docker ports required.
- Read-only container root filesystem support.
- `no-new-privileges` support.
- All Linux capabilities can be dropped.
- Runtime resource limits.
- Runtime GitHub token configuration.
- TLS certificate verification.
