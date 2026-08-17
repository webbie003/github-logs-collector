# Wazuh Integration Guide

This guide describes how to integrate **GitHub Logs Collector v0.2.2** with a Docker-based Wazuh deployment.

GitHub Logs Collector writes structured JSONL to a persistent Docker volume. The Wazuh manager receives **read-only** access to that volume and monitors both collector output streams using Wazuh Logcollector.

The integration is file-based. No inbound listener, webhook endpoint, or direct Docker network connection between GitHub Logs Collector and Wazuh is required.

---

## Architecture

```text
GitHub REST API
       |
       | HTTPS / TCP 443
       v
GitHub Logs Collector
       |
       +---- /var/log/github/events.jsonl
       |
       +---- /var/log/github/collector.jsonl
       |
       v
github_logs Docker volume
       |
       | read-only
       v
Wazuh Manager
       |
       v
Wazuh Indexer
       |
       v
Wazuh Dashboard
```

The collector initiates all network connections. GitHub does not connect directly to the collector.

---

## Event Streams

### GitHub Activity and Security Telemetry

```text
/var/log/github/events.jsonl
```

This stream can contain:

- GitHub account activity
- Push events
- Pull request events
- Issue and issue-comment activity
- Create and delete events
- Release events
- Fork events
- Watch events
- Dependabot alerts
- Code scanning alerts
- Secret scanning alerts
- Security-alert lifecycle changes
- GitHub Actions workflow runs
- Workflow actor and triggering actor
- Workflow branch and commit SHA
- Workflow status and conclusion
- Failed, cancelled, timed-out and other abnormal workflow outcomes
- Failed or abnormal GitHub Actions jobs and steps
- Repository visibility changes
- Private/public state changes
- Archive-state changes
- Default-branch changes

### Collector Operational and Security Telemetry

```text
/var/log/github/collector.jsonl
```

This stream can contain:

- Collector startup and shutdown
- Successful GitHub authentication
- GitHub authentication failures
- GitHub API communication failures
- API timeouts
- GitHub rate-limit events
- Polling-cycle failures
- Security collector failures
- GitHub Actions collection failures
- SQLite state failures
- Filesystem failures
- Successful polling-cycle summaries

---

## Requirements

Recommended GitHub fine-grained token permissions:

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

Do not grant write or administration permissions unless explicitly required.

---

## Files Provided

```text
examples/wazuh/
├── README.md
├── local_rules.xml
└── ossec-localfile.xml
```

- [`README.md`](README.md) contains this integration guide.
- [`local_rules.xml`](local_rules.xml) contains the GitHub Logs Collector Wazuh rules.
- [`ossec-localfile.xml`](ossec-localfile.xml) contains Wazuh Logcollector configuration for both JSONL streams.

---

## 1. Add the Collector to the Wazuh Compose Project

```yaml
  github-logs-collector:
    image: techie003/github-logs-collector:${COLLECTOR_VERSION:-0.2.2}
    container_name: github-logs-collector
    restart: unless-stopped
    init: true

    env_file:
      - .env

    environment:
      GITHUB_API_URL: ${GITHUB_API_URL:-https://api.github.com}
      POLL_INTERVAL: ${POLL_INTERVAL:-300}
      REQUEST_TIMEOUT: ${REQUEST_TIMEOUT:-20}
      MAX_PAGES: ${MAX_PAGES:-10}
      ACTIONS_MAX_RUNS_PER_REPOSITORY: ${ACTIONS_MAX_RUNS_PER_REPOSITORY:-20}

      GITHUB_ACCOUNT_EVENTS_ENABLED: ${GITHUB_ACCOUNT_EVENTS_ENABLED:-true}
      GITHUB_SECURITY_ALERTS_ENABLED: ${GITHUB_SECURITY_ALERTS_ENABLED:-true}
      GITHUB_ACTIONS_ENABLED: ${GITHUB_ACTIONS_ENABLED:-true}
      GITHUB_ACTION_FAILURE_DETAILS_ENABLED: ${GITHUB_ACTION_FAILURE_DETAILS_ENABLED:-true}
      GITHUB_REPOSITORY_SECURITY_STATE_ENABLED: ${GITHUB_REPOSITORY_SECURITY_STATE_ENABLED:-true}

      GITHUB_LOG_FILE: ${GITHUB_LOG_FILE:-/var/log/github/events.jsonl}
      COLLECTOR_LOG_FILE: ${COLLECTOR_LOG_FILE:-/var/log/github/collector.jsonl}
      COLLECTOR_OPERATIONAL_LOG_ENABLED: ${COLLECTOR_OPERATIONAL_LOG_ENABLED:-true}

      STATE_DATABASE: ${STATE_DATABASE:-/var/lib/github-logs-collector/state.db}
      LAST_SUCCESS_FILE: ${LAST_SUCCESS_FILE:-/var/lib/github-logs-collector/last_successful_poll}

      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      HEALTH_MAX_AGE: ${HEALTH_MAX_AGE:-900}

    volumes:
      - github_logs:/var/log/github
      - github_state:/var/lib/github-logs-collector

    security_opt:
      - no-new-privileges:true

    cap_drop:
      - ALL

    read_only: true

    tmpfs:
      - /tmp:size=16M,mode=1777

    pids_limit: 50
    mem_limit: 128m
    cpus: 0.25

    stop_grace_period: 30s

    logging:
      driver: json-file
      options:
        max-size: "20m"
        max-file: "5"

    stdin_open: false
    tty: false

    healthcheck:
      test: ["CMD", "python", "/app/healthcheck.py"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 5m
```

---

## 2. Add Persistent Docker Volumes

Add to the existing top-level `volumes:` block:

```yaml
  github_logs:
  github_state:
```

---

## 3. Mount the Log Volume into Wazuh Manager

Under the existing Wazuh manager `volumes:` section:

```yaml
      - github_logs:/var/log/github:ro
```

The `:ro` option is intentional.

---

## 4. Configure Wazuh Log Collection

Add the contents of [`ossec-localfile.xml`](ossec-localfile.xml) to the persistent Wazuh manager configuration:

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

## 5. Install the Wazuh Rules

Install [`local_rules.xml`](local_rules.xml) through the persistent custom-rule path used by your Wazuh Docker deployment.

The current rule layout is:

```text
110100-110149  GitHub activity, security and Actions events
110150-110199  Collector operational/security events
```

Review this range before deployment to avoid conflicts with existing custom rules.

---

## 6. Rule Coverage

```text
110100  Base GitHub event

110101  PushEvent
110102  PullRequestEvent
110103  Create/Delete
110104  Release
110105  Fork
110106  Issues
110107  Issue Comment
110108  Watch

110110  Dependabot
110111  Code Scanning
110112  Secret Scanning

110120  Actions workflow
110121  Actions failure
110122  Actions cancelled
110123  Actions timed out
110124  Actions abnormal completion
110125  Actions job/step failure

110130  Repository security-state change

110150  Collector operational base
110151  Collector warning
110152  Collector error
110153  Authentication failure
110154  Rate limiting
110155  Poll-cycle failure
110156  SQLite failure
110157  Filesystem failure
110158  API communication problem
110159  Actions collection failure
110160  Security API collection failure
110161  Successful poll summary
```

---

## 7. Dynamic Rule Descriptions

The supplied rules use decoded JSON fields directly in `rule.description`.

This provides useful human-readable context in Wazuh Dashboard without requiring the analyst to open the complete event payload.

Examples:

```text
GitHub PushEvent: webbie003/github-logs-collector pushed by webbie003 ref=main

GitHub Actions: Push on main on webbie003/github-logs-collector triggered_by=webbie003 actor=webbie003 status=completed conclusion=success

GitHub Actions FAILED: Build and Publish on webbie003/github-logs-collector actor=webbie003 triggered_by=webbie003 branch=main

GitHub Dependabot alert #4: webbie003/example-repository state=open

GitHub repository security state changed: webbie003/github-logs-collector

GitHub Logs Collector WARNING: github_rate_limited - GitHub API rate limit reached
```

Descriptions are built from fields such as:

```text
github.repository
github.actor
github.triggering_actor
github.workflow_name
github.status
github.conclusion
github.head_branch
github.ref
github.action
github.alert_number
github.state

log.event
log.level
message
```

Not every field exists in every event type.

---

## 8. Example GitHub Base Rule

```xml
<rule id="110100" level="3">
  <decoded_as>json</decoded_as>
  <field name="source.type">github</field>
  <description>GitHub event: dataset=$(source.dataset) repository=$(github.repository) actor=$(github.actor)</description>
</rule>
```

This is the fallback rule for GitHub events that do not match a more specific child rule.

---

## 9. Example Push Rule

```xml
<rule id="110101" level="3">
  <if_sid>110100</if_sid>
  <field name="github.event">PushEvent</field>
  <description>GitHub PushEvent: $(github.repository) pushed by $(github.actor) ref=$(github.ref)</description>
</rule>
```

---

## 10. Example GitHub Actions Rules

Base workflow event:

```xml
<rule id="110120" level="3">
  <if_sid>110100</if_sid>
  <field name="source.dataset">actions_workflow_run</field>
  <description>GitHub Actions: $(github.workflow_name) on $(github.repository) triggered_by=$(github.triggering_actor) actor=$(github.actor) status=$(github.status) conclusion=$(github.conclusion)</description>
</rule>
```

Failed workflow:

```xml
<rule id="110121" level="8">
  <if_sid>110120</if_sid>
  <field name="github.conclusion">failure</field>
  <description>GitHub Actions FAILED: $(github.workflow_name) on $(github.repository) actor=$(github.actor) triggered_by=$(github.triggering_actor) branch=$(github.head_branch)</description>
</rule>
```

Cancelled workflow:

```xml
<rule id="110122" level="7">
  <if_sid>110120</if_sid>
  <field name="github.conclusion">cancelled</field>
  <description>GitHub Actions CANCELLED: $(github.workflow_name) on $(github.repository) triggered_by=$(github.triggering_actor) branch=$(github.head_branch)</description>
</rule>
```

Timed-out workflow:

```xml
<rule id="110123" level="8">
  <if_sid>110120</if_sid>
  <field name="github.conclusion">timed_out</field>
  <description>GitHub Actions TIMED OUT: $(github.workflow_name) on $(github.repository) triggered_by=$(github.triggering_actor) branch=$(github.head_branch)</description>
</rule>
```

Abnormal job/step:

```xml
<rule id="110125" level="9">
  <if_sid>110100</if_sid>
  <field name="source.dataset">actions_job_failure</field>
  <description>GitHub Actions job failure: $(github.job_name) on $(github.repository) conclusion=$(github.conclusion) run_id=$(github.workflow_run_id)</description>
</rule>
```

---

## 11. Example Security Alert Rules

Dependabot:

```xml
<rule id="110110" level="7">
  <if_sid>110100</if_sid>
  <field name="source.dataset">security_alert</field>
  <field name="github.event">dependabot</field>
  <description>GitHub Dependabot alert #$(github.alert_number): $(github.repository) state=$(github.state)</description>
</rule>
```

Code Scanning:

```xml
<rule id="110111" level="8">
  <if_sid>110100</if_sid>
  <field name="source.dataset">security_alert</field>
  <field name="github.event">code_scanning</field>
  <description>GitHub Code Scanning alert #$(github.alert_number): $(github.repository) state=$(github.state)</description>
</rule>
```

Secret Scanning:

```xml
<rule id="110112" level="10">
  <if_sid>110100</if_sid>
  <field name="source.dataset">security_alert</field>
  <field name="github.event">secret_scanning</field>
  <description>GitHub Secret Scanning alert #$(github.alert_number): $(github.repository) state=$(github.state)</description>
</rule>
```

---

## 12. Repository Security-State Monitoring

The collector monitors:

```text
visibility
private/public state
archived state
default branch
```

Example:

```xml
<rule id="110130" level="8">
  <if_sid>110100</if_sid>
  <field name="source.dataset">repository_security_state</field>
  <description>GitHub repository security state changed: $(github.repository)</description>
</rule>
```

The first observation creates a baseline and does not generate a state-change event.

---

## 13. Collector Operational Rules

Base event:

```xml
<rule id="110150" level="3">
  <decoded_as>json</decoded_as>
  <field name="source.type">collector</field>
  <field name="source.dataset">operational</field>
  <description>GitHub Logs Collector: $(log.event) - $(message)</description>
</rule>
```

Warning:

```xml
<rule id="110151" level="5">
  <if_sid>110150</if_sid>
  <field name="log.level">warning</field>
  <description>GitHub Logs Collector WARNING: $(log.event) - $(message)</description>
</rule>
```

Error:

```xml
<rule id="110152" level="8">
  <if_sid>110150</if_sid>
  <field name="log.level">error</field>
  <description>GitHub Logs Collector ERROR: $(log.event) - $(message)</description>
</rule>
```

Successful polling summary:

```xml
<rule id="110161" level="3">
  <if_sid>110150</if_sid>
  <field name="log.event">poll_complete</field>
  <description>GitHub Logs Collector poll complete: repos=$(details.repositories) events=$(details.account_events) security=$(details.security_events) workflows=$(details.workflow_runs) abnormal_jobs=$(details.abnormal_action_jobs)</description>
</rule>
```

---

## 14. Verify Both JSONL Streams

Inside the collector:

```bash
docker exec github-logs-collector   ls -lah /var/log/github
```

Expected:

```text
events.jsonl
collector.jsonl
```

Check GitHub telemetry:

```bash
docker exec github-logs-collector   tail -n 5 /var/log/github/events.jsonl
```

Check operational telemetry:

```bash
docker exec github-logs-collector   tail -n 5 /var/log/github/collector.jsonl
```

---

## 15. Verify Wazuh Can Read Both Files

```bash
docker exec <WAZUH_MANAGER_CONTAINER>   ls -lah /var/log/github
```

Then:

```bash
docker exec <WAZUH_MANAGER_CONTAINER>   tail -n 5 /var/log/github/events.jsonl
```

and:

```bash
docker exec <WAZUH_MANAGER_CONTAINER>   tail -n 5 /var/log/github/collector.jsonl
```

---

## 16. Test Rules with `wazuh-logtest`

Extract one event:

```bash
docker exec github-logs-collector   tail -n 1 /var/log/github/events.jsonl
```

Copy the complete JSON object.

Run:

```bash
docker exec -it <WAZUH_MANAGER_CONTAINER>   /var/ossec/bin/wazuh-logtest
```

Paste the event.

For GitHub Actions events, useful decoded fields include:

```text
source.type
source.dataset

collector.name
collector.version
collector.mode

github.repository
github.workflow_run_id
github.workflow_id
github.workflow_name
github.run_number
github.run_attempt
github.trigger_event
github.status
github.conclusion
github.head_branch
github.head_sha
github.actor
github.triggering_actor
```

The final matched rule should include the contextual `rule.description`.

---

## 17. Test Collector Operational Events

Extract one event:

```bash
docker exec github-logs-collector   tail -n 1 /var/log/github/collector.jsonl
```

Run:

```bash
docker exec -it <WAZUH_MANAGER_CONTAINER>   /var/ossec/bin/wazuh-logtest
```

Useful decoded fields include:

```text
source.type
source.dataset

collector.name
collector.version
collector.mode

log.level
log.event
message

details.repositories
details.account_events
details.security_events
details.workflow_runs
details.abnormal_action_jobs
```

---

## 18. Recommended Wazuh Dashboard Columns

Useful Wazuh Dashboard columns include:

```text
timestamp
rule.description
rule.level
rule.id

data.github.repository
data.github.actor
data.github.triggering_actor
data.github.workflow_name
data.github.status
data.github.conclusion

data.log.event
data.log.level
```

Because the rules now use dynamic descriptions, `rule.description` is recommended as a primary human-readable dashboard column.

For v0.2.2 events, prefer:

```text
data.github.repository
```

rather than older/custom fields such as:

```text
data.github.repo
```

when creating new dashboard views.

---

## 19. Suggested Wazuh Alert Levels

| Event | Suggested Level |
|:---|---:|
| Normal account activity | 3 |
| Successful Actions workflow | 3 |
| Successful collector poll | 3 |
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
| Actions collection failure | 8 |
| Security API collection failure | 8 |
| Abnormal Actions job/step | 9 |
| Secret scanning alert | 10 |
| Collector authentication failure | 10 |
| Collector polling failure | 10 |
| SQLite failure | 10 |
| Filesystem failure | 10 |

Tune these levels for the environment.

---

## 20. Troubleshooting Dynamic Descriptions

A dynamic `rule.description` can only populate fields present in the decoded event.

If a description contains a blank or unexpected value:

1. capture one raw JSON event
2. run `wazuh-logtest`
3. inspect the decoded field names
4. confirm the corresponding field exists in that event type
5. confirm the rule references the current v0.2.2 schema

The current collector uses:

```text
github.repository
```

which normally appears in indexed Wazuh events as:

```text
data.github.repository
```

Do not assume older custom field names such as:

```text
data.github.repo
```

remain valid.

---

## 21. Troubleshooting Logcollector

Inspect Wazuh Logcollector messages:

```bash
docker exec <WAZUH_MANAGER_CONTAINER>   grep -i logcollector   /var/ossec/logs/ossec.log | tail -n 100
```

Verify the configured paths:

```bash
docker exec <WAZUH_MANAGER_CONTAINER>   grep -A3 -B1   '/var/log/github'   /var/ossec/etc/ossec.conf
```

Both should appear:

```text
/var/log/github/events.jsonl
/var/log/github/collector.jsonl
```

---

## 22. Troubleshooting GitHub Actions Events

Verify:

```env
GITHUB_ACTIONS_ENABLED=true
```

and:

```text
Actions: Read-only
```

Inspect events:

```bash
docker exec github-logs-collector   grep '"dataset":"actions_'   /var/log/github/events.jsonl | tail -n 20
```

For detailed abnormal job/step events:

```env
GITHUB_ACTION_FAILURE_DETAILS_ENABLED=true
```

Successful workflows do not generate separate successful job/step events.

---

## 23. Troubleshooting Repository Security State

Verify:

```env
GITHUB_REPOSITORY_SECURITY_STATE_ENABLED=true
```

The first observation creates a baseline.

Later changes produce:

```text
source.dataset=repository_security_state
```

Do not routinely delete `github_state`, because the baseline is stored in persistent state.

---

## 24. Security Recommendations

- Keep the GitHub token read-only.
- Grant `Actions: Read-only` only when Actions telemetry is enabled.
- Never store the token in the Docker image.
- Protect `.env` with restrictive permissions.
- Do not publish collector ports.
- Keep the collector root filesystem read-only.
- Drop all Linux capabilities.
- Enable `no-new-privileges`.
- Run as the non-root collector user.
- Keep Wazuh access to `github_logs` read-only.
- Protect the `github_logs` and `github_state` volumes.
- Treat both JSONL streams as security-sensitive.
- Test custom rules with `wazuh-logtest` before relying on alerting.

---

## 25. Final Validation Checklist

```text
GitHub API authentication succeeds
        |
        v
Collector discovers repositories
        |
        v
Collector writes events.jsonl
        |
        v
Collector writes collector.jsonl
        |
        v
SQLite state.db exists
        |
        v
Docker health becomes healthy
        |
        v
Wazuh manager sees github_logs volume
        |
        v
Wazuh can read events.jsonl
        |
        v
Wazuh can read collector.jsonl
        |
        v
Wazuh Logcollector monitors both files
        |
        v
JSON fields decode correctly
        |
        v
GitHub rules match in wazuh-logtest
        |
        v
Dynamic rule.description fields populate
        |
        v
Collector operational rules match
        |
        v
Events appear in Wazuh Dashboard
```

---

## Related Documentation

[README.md](../../README.md)
[SECURITY.md](../../SECURITY.md)
[SECURITY-STATUS.md](../../docs/SECURITY-STATUS.md)
[GITHUB_SECURITY_SETUP.md](../../docs/GITHUB_SECURITY_SETUP.md)
[ossec-localfile.xml](ossec-localfile.xml)
[local_rules.xml](local_rules.xml)
[CHANGELOG.md](../../CHANGELOG.md)
