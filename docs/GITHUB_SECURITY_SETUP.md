# GitHub Security Setup

This guide describes the recommended GitHub security configuration for **GitHub Logs Collector v0.2.2**.

The collector is designed for read-only GitHub access. Grant only the permissions required by enabled collection sources.

---

## Recommended Fine-Grained Personal Access Token

Recommended permissions:

```text
Account:
  Events: Read-only

Repository:
  Metadata: Read-only
  Actions: Read-only
  Dependabot alerts: Read-only
  Code scanning alerts: Read-only
  Secret scanning alerts: Read-only
```

`Actions: Read-only` is required only when GitHub Actions telemetry is enabled.

Do not grant write or administration permissions unless a future feature explicitly requires them.

---

## Repository Access

Restrict the token to only the repositories that should be monitored where practical.

Repository discovery and security-feature availability are separate conditions: a repository may be visible to the token while a specific security API remains disabled or unavailable.

---

## Dependency Graph and Dependabot

For repositories that should provide dependency vulnerability telemetry, enable:

```text
Dependency graph
Dependabot alerts
```

Dependabot security updates are optional.

The collector uses the Dependabot alerts API in read-only mode and can record alert lifecycle changes where the API exposes them.

---

## Code Scanning

Enable Code Scanning / CodeQL where available.

The collector requires:

```text
Code scanning alerts: Read-only
```

---

## Secret Scanning

Enable where available:

```text
Secret scanning
Push protection
```

The collector requires:

```text
Secret scanning alerts: Read-only
```

Treat secret-scanning output as sensitive security data.

---

## GitHub Actions Monitoring

Enable collector-side Actions monitoring with:

```env
GITHUB_ACTIONS_ENABLED=true
```

Grant:

```text
Actions: Read-only
```

The collector can record:

- workflow name
- workflow run ID
- workflow ID
- run number
- run attempt
- trigger event
- status
- conclusion
- branch/tag
- commit SHA
- actor
- triggering actor

---

## Abnormal Workflow Job and Step Monitoring

Enable:

```env
GITHUB_ACTION_FAILURE_DETAILS_ENABLED=true
```

Detailed job/step collection is focused on abnormal outcomes:

```text
failure
cancelled
timed_out
stale
action_required
startup_failure
```

Successful workflow runs are still recorded, but successful jobs/steps are not emitted separately.

Raw GitHub Actions console logs are not downloaded. This reduces noise and avoids unnecessarily collecting potentially sensitive build output.

---

## Repository Security-State Monitoring

Enable:

```env
GITHUB_REPOSITORY_SECURITY_STATE_ENABLED=true
```

The collector monitors only security-relevant repository state:

```text
visibility
private/public state
archived/unarchived state
default branch
```

The first observation creates a baseline. Later changes generate security-state events.

Stars, watchers, open-issue counts and fork counters are intentionally not monitored as security-state telemetry.

---

## Existing Repositories

Review existing repositories individually. Settings intended for future repositories do not necessarily configure existing repositories retrospectively.

Verify where applicable:

```text
Dependency graph
Dependabot alerts
Secret scanning
Push protection
Code scanning / CodeQL
GitHub Actions access
```

---

## HTTP 401

An HTTP `401` normally indicates authentication failure. Check token validity, expiration/revocation, configured username and runtime secret injection.

Never print the token or Authorization header while troubleshooting.

---

## HTTP 403

An HTTP `403` can indicate insufficient permission, repository policy restrictions, API rate limiting, or unavailable security features.

The collector detects rate-limit responses separately and backs off instead of terminating.

---

## HTTP 404

An HTTP `404` from a repository security endpoint can mean the feature is disabled, unsupported, outside token scope or inaccessible to the authenticated account.

Unavailable repository security endpoints are handled independently.

---

## Token Storage

Supply the GitHub token at runtime.

For local/homelab use:

```bash
chmod 600 .env
```

Do not:

- commit `.env`
- place the token in the Dockerfile
- use the token as a build argument
- hard-code it into Python
- print it in logs
- expose the Authorization header

---

## Validation

Review collector runtime logs:

```bash
docker logs github-logs-collector
```

Inspect GitHub events:

```bash
docker exec github-logs-collector \
  tail -n 20 /var/log/github/events.jsonl
```

Inspect collector operational telemetry:

```bash
docker exec github-logs-collector \
  tail -n 20 /var/log/github/collector.jsonl
```

Inspect Actions events:

```bash
docker exec github-logs-collector \
  grep '"dataset":"actions_' /var/log/github/events.jsonl | tail -n 20
```

---

## Related Documentation

- [Main README](../README.md)
- [Security Policy](../SECURITY.md)
- [Wazuh Integration](../examples/wazuh/README.md)
- [Release History](../CHANGELOG.md)
- [SECURITY-STATUS.md](SECURITY-STATUS.md)
