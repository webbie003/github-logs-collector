# Wazuh Integration Guide

This guide describes how to integrate **GitHub Logs Collector v0.2.2** with a Docker-based Wazuh deployment.

GitHub Logs Collector writes structured JSONL to a persistent Docker volume. The Wazuh manager receives **read-only** access to the same volume and monitors both output streams using Wazuh Logcollector.

No inbound collector listener, webhook endpoint or direct Docker network connection between the collector and Wazuh is required.

---

## Event Streams

GitHub activity and security telemetry:

```text
/var/log/github/events.jsonl
```

Collector operational/security telemetry:

```text
/var/log/github/collector.jsonl
```

Wazuh should monitor both files.

---

## Recommended GitHub Token Permissions

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

---

## Add the Collector to the Wazuh Compose Project

Use the collector service from [`../docker-compose/docker-compose.yml`](../docker-compose/docker-compose.yml), or merge the same service definition into the existing Wazuh Compose project.

The collector requires these named volumes:

```yaml
volumes:
  github_logs:
  github_state:
```

---

## Mount the Log Volume into Wazuh Manager

Under the existing Wazuh manager `volumes:` section, add:

```yaml
- github_logs:/var/log/github:ro
```

The `:ro` mount is intentional. The collector writes; Wazuh reads.

---

## Configure Wazuh Logcollector

Add the contents of [`ossec-localfile.xml`](ossec-localfile.xml) to the persistent Wazuh manager configuration.

Required entries:

```xml
<localfile>
  <log_format>json</log_format>
  <location>/var/log/github/events.jsonl</location>
</localfile>

<localfile>
  <log_format>json</log_format>
  <location>/var/log/github/collector.jsonl</location>
</localfile>
```

---

## Install the Wazuh Rules

Install [`local_rules.xml`](local_rules.xml) using the persistent custom-rule path for the Wazuh Docker deployment.

The examples use:

```text
110100-110149  GitHub activity/security/Actions
110150-110199  Collector operational/security
```

Review the rule IDs before deployment to avoid conflicts.

---

## Recreate the Manager if the Volume Mount Is New

If `github_logs` is being mounted into Wazuh for the first time:

```bash
docker compose up -d --force-recreate wazuh.manager
```

If the volume is already mounted and only XML/rules changed:

```bash
docker restart <WAZUH_MANAGER_CONTAINER>
```

---

## Verify the Collector Writes Both Files

```bash
docker exec github-logs-collector \
  ls -lah /var/log/github
```

Expected:

```text
events.jsonl
collector.jsonl
```

Check both streams:

```bash
docker exec github-logs-collector \
  tail -n 5 /var/log/github/events.jsonl
```

```bash
docker exec github-logs-collector \
  tail -n 5 /var/log/github/collector.jsonl
```

---

## Verify Wazuh Can Read Both Files

```bash
docker exec <WAZUH_MANAGER_CONTAINER> \
  ls -lah /var/log/github
```

```bash
docker exec <WAZUH_MANAGER_CONTAINER> \
  tail -n 5 /var/log/github/events.jsonl
```

```bash
docker exec <WAZUH_MANAGER_CONTAINER> \
  tail -n 5 /var/log/github/collector.jsonl
```

---

## Test with wazuh-logtest

Get a GitHub event:

```bash
docker exec github-logs-collector \
  tail -n 1 /var/log/github/events.jsonl
```

Then run:

```bash
docker exec -it <WAZUH_MANAGER_CONTAINER> \
  /var/ossec/bin/wazuh-logtest
```

Paste the JSON event.

Repeat with an operational event from:

```text
/var/log/github/collector.jsonl
```

Useful operational fields include:

```text
source.type
source.dataset
log.level
log.event
message
```

---

## Suggested Alert Priorities

| Event | Suggested Level |
|:---|---:|
| Normal account activity | 3 |
| Successful Actions workflow | 3 |
| Create/delete/release/fork activity | 4 |
| Collector warning | 5 |
| Cancelled workflow | 7 |
| API rate limiting | 7 |
| Dependabot alert | 7 |
| API communication problem | 7 |
| Code scanning alert | 8 |
| Failed workflow | 8 |
| Timed-out workflow | 8 |
| Repository security-state change | 8 |
| Abnormal Actions job/step | 9 |
| Secret scanning alert | 10 |
| Collector authentication failure | 10 |
| Collector polling failure | 10 |
| SQLite failure | 10 |
| Filesystem failure | 10 |

Tune these values for the environment.

---

## Troubleshooting

Collector runtime logs:

```bash
docker logs github-logs-collector
```

Wazuh Logcollector messages:

```bash
docker exec <WAZUH_MANAGER_CONTAINER> \
  grep -i logcollector /var/ossec/logs/ossec.log | tail -n 100
```

Verify the configured paths:

```bash
docker exec <WAZUH_MANAGER_CONTAINER> \
  grep -A3 -B1 '/var/log/github' /var/ossec/etc/ossec.conf
```

Verify mounts:

```bash
docker inspect github-logs-collector \
  --format '{{json .Mounts}}'
```

```bash
docker inspect <WAZUH_MANAGER_CONTAINER> \
  --format '{{json .Mounts}}'
```

Both containers should reference the same `github_logs` volume.

---

## Security Recommendations

- Keep the GitHub token read-only.
- Protect `.env` with restrictive permissions.
- Do not publish collector ports.
- Keep the root filesystem read-only.
- Drop all Linux capabilities.
- Keep `no-new-privileges` enabled.
- Keep Wazuh access to `github_logs` read-only.
- Protect both JSONL streams and the SQLite state volume.
- Do not routinely delete `github_state`; it contains deduplication and repository security-state baselines.
- Test rules using `wazuh-logtest` before relying on alerting.

---

## Related Documentation

- [Main README](../../README.md)
- [Security Policy](../../SECURITY.md)
- [GitHub Security Setup](../../docs/GITHUB_SECURITY_SETUP.md)
- [Logcollector Configuration](ossec-localfile.xml)
- [Custom Rules](local_rules.xml)
- [Release History](../../CHANGELOG.md)
