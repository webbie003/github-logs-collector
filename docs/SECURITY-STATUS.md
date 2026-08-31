# Container Security Status

This file is generated automatically by the
**Trivy Security Scan** GitHub Actions workflow.

Manual edits may be overwritten.

## Current Status

**Status:** `ATTENTION REQUIRED`

One or more CRITICAL or HIGH vulnerabilities were detected.

## Latest Scan

| Property | Value |
|:---|:---|
| Scan time | `2026-08-31 08:51:23 UTC` |
| Commit | `fa8dd1822ce314ab1fa86562288ac161160df484` |
| Scanner | `Trivy` |
| Scan type | Container image vulnerability scan |
| Policy gate | `CRITICAL,HIGH` |

## Vulnerability Summary

| Severity | Findings |
|:---|---:|
| Critical | 0 |
| High | 2 |
| Medium | 6 |
| Low | 12 |
| Unknown | 0 |
| **Total** | **20** |

## Scanned Targets

- `github-logs-collector:security-scan (alpine 3.24.1)`
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

[View this workflow run](https://github.com/webbie003/github-logs-collector/actions/runs/33374757568)
