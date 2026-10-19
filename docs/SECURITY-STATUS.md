# Container Security Status

This file is generated automatically by the
**Trivy Security Scan** GitHub Actions workflow.

Manual edits may be overwritten.

## Current Status

**Status:** `PASS`

No CRITICAL or HIGH vulnerabilities were detected in the current container image.

## Latest Scan

| Property | Value |
|:---|:---|
| Scan time | `2026-10-19 08:02:03 UTC` |
| Commit | `aab2e33519f5bc73cfd74866f9f1a5116072ef3e` |
| Scanner | `Trivy` |
| Scan type | Container image vulnerability scan |
| Policy gate | `CRITICAL,HIGH` |

## Vulnerability Summary

| Severity | Findings |
|:---|---:|
| Critical | 0 |
| High | 0 |
| Medium | 1 |
| Low | 0 |
| Unknown | 0 |
| **Total** | **1** |

## Scanned Targets

- `github-logs-collector:security-scan (alpine 3.24.2)`
- `Python`

## Security Policy

Release publication is blocked when the release-gate scan
detects one or more `CRITICAL` or `HIGH` vulnerabilities.

`MEDIUM`, `LOW`, and `UNKNOWN` findings are reported for
visibility but do not currently block publication.

The repository is also scanned separately for accidentally
committed secrets such as credentials, API tokens, private
keys, and other sensitive values.

Vulnerability data changes over time as scanner databases and
upstream advisories are updated. A clean result is therefore
a point-in-time assessment rather than a permanent guarantee.

## Detailed Results

High and Critical container vulnerability findings and
repository secret findings are uploaded separately to the
GitHub repository Security / Code Scanning interface.

[View this workflow run](https://github.com/webbie003/github-logs-collector/actions/runs/39219769562)
