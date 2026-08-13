# Security Policy

## Supported Versions

Security updates are targeted at the currently maintained release.

| Version | Supported |
|---|---|
| 0.2.1 | Yes |
| 0.2.0 | Upgrade recommended |
| < 0.2.0 | No |

Users should run the latest maintained container image whenever practical.

---

# Reporting a Vulnerability

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

# Sensitive Information

Never include the following in public issues, pull requests, screenshots, diagnostic output, or commits:

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

# Security Design

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

---

# Alpine Runtime

Version `0.2.1` uses:

```text
python:3.13.15-alpine3.24
```

as the runtime base image.

The change reduces the operating-system package footprint compared with the previous Debian slim runtime.

A smaller runtime image reduces the number of packages that require patching and the amount of unnecessary executable functionality present inside the production container.

The base image should still be rebuilt regularly using:

```bash
docker build --pull --no-cache ...
```

to obtain current upstream security fixes.

---

# Runtime Packaging Tools

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

# Container Identity

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

# Read-Only Root Filesystem

The recommended Compose configuration uses:

```yaml
read_only: true
```

Only explicitly mounted log/state volumes and the memory-backed temporary directory should remain writable.

---

# Linux Capabilities

The collector requires no additional Linux capabilities.

Recommended:

```yaml
cap_drop:
  - ALL
```

---

# No New Privileges

Enable:

```yaml
security_opt:
  - no-new-privileges:true
```

to prevent processes from acquiring additional privileges through executable permission mechanisms.

---

# Docker Socket

Do not mount:

```text
/var/run/docker.sock
```

into the collector.

The application does not require Docker daemon access.

Providing Docker socket access would significantly increase the impact of a container compromise.

---

# Network Exposure

The collector performs outbound HTTPS requests to GitHub.

It does not require:

- inbound Internet access
- published Docker ports
- reverse proxy access
- host networking

No Docker `ports:` configuration should normally be present.

---

# GitHub Credentials

Use a fine-grained personal access token where possible.

Grant only the read permissions required for the features being collected.

Typical permissions include:

```text
Account:
  Events: Read

Repository:
  Metadata: Read
  Dependabot alerts: Read
  Code scanning alerts: Read
  Secret scanning alerts: Read
```

Restrict repository access to the intended monitoring scope.

Do not grant write or administration permissions unless explicitly required by a future feature.

---

# GitHub Security Features

This `SECURITY.md` file defines the project's vulnerability-reporting policy.

It does **not** enable GitHub repository security products.

Features such as:

- dependency graph
- Dependabot alerts
- secret scanning
- push protection
- code scanning / CodeQL

must be configured independently.

See:

```text
docs/GITHUB_SECURITY_SETUP.md
```

for setup guidance.

---

# Event Data

Collector JSONL output may contain security-sensitive information including:

- private repository names
- branch names
- commit metadata
- internal project identifiers
- vulnerability information
- code scanning findings
- secret-scanning metadata

Restrict access to:

```text
/var/log/github/events.jsonl
```

and downstream SIEM storage.

---

# Persistent State

The collector stores deduplication state in:

```text
/var/lib/github-logs-collector/state.db
```

This volume does not normally contain the GitHub authentication token but should still be protected against unnecessary modification.

---

# Health Monitoring

Version `0.2.1` includes a health probe that validates successful collector progress.

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
- the application is alive but no longer making progress

The health probe operates locally and does not require the GitHub token.

---

# TLS

TLS certificate verification must remain enabled for GitHub API requests.

Do not disable HTTPS certificate verification to work around certificate or proxy failures.

---

# Dependency Management

Application dependencies are defined in:

```text
requirements.txt
```

Dependency upgrades should be performed through source control followed by a clean Docker rebuild.

Do not install additional Python packages interactively into production containers.

---

# Vulnerability Scanning

Container images should be scanned before release.

Example:

```bash
trivy image \
  --severity CRITICAL,HIGH \
  github-logs-collector:0.2.1
```

The `0.2.1` release candidate was tested after migration to Alpine and removal of runtime Python packaging tooling.

At the time of release testing, Trivy reported:

```text
CRITICAL: 0
HIGH:     0
```

Scanner databases change continuously.

A previously clean image may receive findings later as new vulnerabilities are disclosed.

A zero-finding result must therefore not be interpreted as proof that an image is permanently vulnerability-free.

---

# Image Updates

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

# Secrets in Docker

The GitHub token must be supplied at runtime.

Do not:

- add the token to the Dockerfile
- use the token as an image build argument
- commit a populated `.env`
- embed the token in application source
- log the Authorization header

For local/homelab deployments, protect `.env`:

```bash
chmod 600 .env
```

For higher-security environments, use an appropriate external secret-management mechanism.

---

# Release Security Checklist

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
- [ ] Confirm JSONL output works
- [ ] Confirm successful-poll timestamp updates
- [ ] Confirm Docker health status becomes healthy
- [ ] Run Trivy vulnerability scanning
- [ ] Run Trivy secret scanning
- [ ] Check source control for accidentally committed tokens
- [ ] Review `.env` exclusion
- [ ] Review staged Git changes before release

---

# Security Is Layered

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
