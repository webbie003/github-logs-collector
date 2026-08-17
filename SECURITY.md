# Security Policy

## Supported Versions

Security updates are targeted at the currently maintained release.

| Version | Supported |
|---|---|
| 0.2.2 | Yes |
| 0.2.1 | Upgrade recommended |
| 0.2.0 | Upgrade recommended |
| < 0.2.0 | No |

Users should run the latest maintained container image whenever practical.

---

## Reporting a Vulnerability

Do not publicly disclose a suspected vulnerability before it has been reviewed.

If you identify a vulnerability in `github-logs-collector`, report it privately through the repository's GitHub security reporting capability where available.

Include sufficient information to reproduce and assess the issue:

- affected component or file
- affected version or commit
- description of the vulnerability
- reproduction steps
- expected and actual behaviour
- potential security impact
- relevant logs or screenshots with secrets removed
- suggested remediation, if known

Do not include authentication credentials or discovered secrets.

---

## Sensitive Information

Never include the following in public issues, pull requests, screenshots, diagnostic output or commits:

- GitHub personal access tokens
- API keys
- passwords
- private keys
- session tokens
- authentication headers
- internal credentials
- secrets discovered through secret scanning
- unredacted sensitive repository information

If a credential is exposed, revoke or rotate it immediately.

---

## Security Design

GitHub Logs Collector follows a least-privilege and reduced-attack-surface design.

Recommended controls include:

- dedicated GitHub credentials
- read-only GitHub permissions
- no inbound collector listener
- no published Docker ports
- non-root execution
- read-only root filesystem
- `no-new-privileges`
- all Linux capabilities dropped
- no Docker socket access
- persistent writes limited to log and state volumes
- memory-backed `/tmp`
- resource limits
- protected runtime secrets
- regular image rebuilds
- vulnerability scanning
- explicit container version pinning
- separate operational monitoring
- persistent event deduplication
- persistent repository security-state baselines

---

## Alpine Runtime

Version `0.2.1` introduced:

```text
python:3.13.15-alpine3.24
```

as the runtime base image.

The change reduced the operating-system package footprint compared with the previous Debian slim runtime.

A smaller runtime image reduces the number of packages that require patching and the amount of unnecessary executable functionality present inside the production container.

The base image should still be rebuilt regularly using:

```bash
docker build --pull --no-cache ...
```

to obtain current upstream security fixes.

---

## Runtime Packaging Tools

Python `pip` is required during image construction to install application dependencies.

It is **not required by the running collector**.

The Docker build therefore removes pip after dependency installation.

This means the final runtime image intentionally does not support:

```bash
python -m pip
```

Runtime package installation should not be performed inside a running collector container.

Dependency changes should instead be made through:

```text
requirements.txt
```

followed by a clean image rebuild.

This approach:

- reduces runtime attack surface
- prevents unnecessary package-management operations
- removes pip's unused vendored libraries
- makes dependency changes reproducible through the Docker build process

---

## Container Identity

The collector runs as:

```text
UID 10001
GID 10001
```

The runtime user does not require root privileges.

Persistent writable paths are limited to:

```text
/var/log/github
/var/lib/github-logs-collector
```

and `/tmp` should be provided using a Docker `tmpfs`.

---

## Read-Only Root Filesystem

The recommended Compose configuration uses:

```yaml
read_only: true
```

Only explicitly mounted log/state volumes and the memory-backed temporary directory should remain writable.

---

## Linux Capabilities

The collector requires no additional Linux capabilities.

Recommended:

```yaml
cap_drop:
  - ALL
```

---

## No New Privileges

Enable:

```yaml
security_opt:
  - no-new-privileges:true
```

to prevent processes from acquiring additional privileges through executable permission mechanisms.

---

## Docker Socket

Do not mount:

```text
/var/run/docker.sock
```

into the collector.

The application does not require Docker daemon access.

Providing Docker socket access would significantly increase the impact of a container compromise.

---

## Network Exposure

The collector performs outbound HTTPS requests to GitHub.

It does not require:

- inbound Internet access
- published Docker ports
- reverse proxy access
- host networking

No Docker `ports:` configuration should normally be present.

---

## GitHub Credentials

Use a fine-grained personal access token where possible.

Grant only the read permissions required for the features being collected.

Typical permissions include:

```text
Account:
  Events: Read

Repository:
  Metadata: Read
  Actions: Read
  Dependabot alerts: Read
  Code scanning alerts: Read
  Secret scanning alerts: Read
```

Restrict repository access to the intended monitoring scope.

`Actions: Read` is required only when GitHub Actions telemetry is enabled.

Do not grant write or administration permissions unless explicitly required by a future feature.

---

## GitHub Security Features

This `SECURITY.md` file defines the project's vulnerability-reporting policy.

It does **not** enable GitHub repository security products.

Features such as:

- dependency graph
- Dependabot alerts
- secret scanning
- push protection
- code scanning / CodeQL

must be configured independently.

See [docs/GITHUB_SECURITY_SETUP.md](docs/GITHUB_SECURITY_SETUP.md) for setup guidance.

---

## Event Data

Collector JSONL output may contain security-sensitive information including:

- private repository names
- branch and default-branch names
- commit SHA and metadata
- workflow names
- workflow actor and triggering actor
- GitHub Actions job and failed-step metadata
- repository visibility changes
- vulnerability information
- code scanning findings
- secret-scanning metadata
- original GitHub API payloads

Restrict access to both collector streams:

```text
/var/log/github/events.jsonl
/var/log/github/collector.jsonl
```

and downstream SIEM storage.

---

## Collector Operational Telemetry

The collector can maintain a separate operational/security stream:

```text
/var/log/github/collector.jsonl
```

This stream may contain:

- collector startup and shutdown
- successful GitHub authentication
- authentication failures
- GitHub API communication failures
- API timeouts
- rate-limit conditions
- polling failures
- security collector failures
- GitHub Actions collection failures
- SQLite state failures
- filesystem failures
- successful polling summaries

It does not intentionally contain the GitHub authentication token or HTTP Authorization headers.

The operational stream should be protected and retained according to the same security requirements as the primary event stream.

---

## Persistent State

The collector stores deduplication and repository security-state baselines in:

```text
/var/lib/github-logs-collector/state.db
```

This volume does not normally contain the GitHub authentication token but should still be protected against unnecessary access or modification.

Deleting the persistent state may cause previously observed events to be collected again and repository security-state baselines to be recreated.

---

## Health Monitoring

Version `0.2.1` introduced a health probe that validates successful collector progress.

After every successful polling cycle the application updates:

```text
/var/lib/github-logs-collector/last_successful_poll
```

The health check verifies that this timestamp remains sufficiently recent.

Default:

```env
POLL_INTERVAL=300
HEALTH_MAX_AGE=900
```

This allows approximately three normal polling intervals before the container is marked unhealthy.

This detects failures where:

- the process remains running but polling stalls
- GitHub API failures repeatedly prevent successful cycles
- collector state operations repeatedly fail
- the application remains alive but no longer makes useful progress

The health probe operates locally and does not require the GitHub token.

---

## TLS

TLS certificate verification must remain enabled for GitHub API requests.

Do not disable HTTPS certificate verification to work around certificate or proxy failures.

---

## Dependency Management

Application dependencies are defined in:

```text
requirements.txt
```

Dependency upgrades should be performed through source control followed by a clean Docker rebuild.

Do not install additional Python packages interactively into production containers.

---

## Vulnerability Scanning

Container images are automatically scanned before release, results are published in:

[Container Security Status](docs/SECURITY-STATUS.md)

The status document is generated by the repository's Trivy GitHub Actions workflow and records the latest vulnerability counts by severity.

The automated release gate prevents publication when a release-candidate image contains `CRITICAL` or `HIGH` vulnerability findings.

---

## Image Updates

Use:

```bash
docker build \
  --pull \
  --no-cache \
  ...
```

when preparing a release.

This ensures the current upstream base image is retrieved instead of silently reusing an older local layer.

---

## Secrets in Docker

The GitHub token must be supplied at runtime.

Do not:

- add the token to the Dockerfile
- use the token as an image build argument
- commit a populated `.env`
- embed the token in application source
- log the Authorization header

For local or homelab deployments, protect `.env`:

```bash
chmod 600 .env
```

For higher-security environments, use an appropriate external secret-management mechanism.

---

## GitHub Actions Telemetry

When GitHub Actions monitoring is enabled, the collector can record:

- workflow name
- workflow actor
- triggering actor
- branch or tag
- commit SHA
- workflow status
- workflow conclusion
- run number
- run attempt

Detailed job/step information is intentionally focused on abnormal workflow outcomes such as:

```text
failure
cancelled
timed_out
stale
action_required
startup_failure
```

Raw GitHub Actions console logs are not downloaded by default.

This reduces unnecessary data collection and avoids ingesting large quantities of potentially sensitive build output.

---

## Repository Security-State Monitoring

The collector intentionally limits repository security-state monitoring to:

```text
visibility
private/public state
archived/unarchived state
default branch
```

The first observation creates a persistent baseline.

Subsequent changes are written as security-relevant events with before/after values.

Popularity and project-analytics counters such as stars, watchers, open-issue counts and fork counts are intentionally not monitored as security-state events.

---

## Release Security Checklist

Before publishing a release:

- [ ] Build using `--pull --no-cache`
- [ ] Confirm the image runs as UID/GID `10001:10001`
- [ ] Confirm the root filesystem can remain read-only
- [ ] Confirm all Linux capabilities are dropped
- [ ] Confirm `no-new-privileges` is enabled
- [ ] Confirm no Docker ports are published
- [ ] Confirm Docker socket access is absent
- [ ] Confirm pip is absent from the runtime image
- [ ] Confirm application imports succeed
- [ ] Confirm SQLite state persists
- [ ] Confirm event deduplication works
- [ ] Confirm repository security-state baselines persist
- [ ] Confirm `/var/log/github/events.jsonl` is written
- [ ] Confirm `/var/log/github/collector.jsonl` is written
- [ ] Confirm successful-poll timestamp updates
- [ ] Confirm Docker health status becomes healthy
- [ ] Confirm GitHub Actions events are collected when enabled
- [ ] Confirm security-alert lifecycle events are collected
- [ ] Run Trivy vulnerability scanning
- [ ] Run Trivy secret scanning
- [ ] Check source control for accidentally committed tokens
- [ ] Review `.env` exclusion
- [ ] Review staged Git changes before release

---

## Security Is Layered

A clean vulnerability scan is only one control.

Security also depends on:

- least privilege
- secure credential management
- GitHub configuration
- container hardening
- restricted file access
- prompt patching
- monitoring
- vulnerability management
- secure operational practices

The project should not weaken one security control merely to obtain a cleaner scanner report.
