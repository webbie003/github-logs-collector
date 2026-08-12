# GitHub Security Setup

This document describes the GitHub security settings required or recommended for repositories monitored by `github-logs-collector`.

## Objectives

The configuration is intended to:

- Enable GitHub security detections where available
- Allow `github-logs-collector` to retrieve repository security alerts
- Reduce the chance that new repositories are created without baseline security controls
- Ensure existing repositories are reviewed and configured individually
- Apply least-privilege access to the collector credential
- Improve central security visibility through Wazuh or another SIEM

## Recommended Security Features

Enable the following features where supported and appropriate:

- Dependabot alerts
- Secret scanning
- Push protection
- Code scanning / CodeQL

These features are separate from the repository's `SECURITY.md` policy.

## New Repositories

Where GitHub provides account-level or organization-level controls, enable the applicable options so security features are automatically enabled for future repositories.

Recommended future-repository defaults include:

- Dependabot alerts
- Secret scanning
- Push protection
- Code scanning / CodeQL where an appropriate default configuration is available

Automatic settings for future repositories reduce administrative overhead, but they do not replace validation of existing repositories.

# Existing Repository Security Monitoring Requirements

> **Important:** Enabling GitHub security features for future repositories does **not necessarily enable those features on repositories that already exist**.

The `github-logs-collector` can only retrieve security alerts from a repository when the corresponding GitHub security feature is enabled and the collector's GitHub credential has permission to read those alerts.

Existing repositories that are to be monitored must therefore be reviewed **individually**.

## Required Settings for Existing Repositories

For **each existing repository** that should be monitored:

1. Open the repository in GitHub.
2. Select **Settings**.
3. Select **Advanced Security** or **Code security and analysis**, depending on the GitHub interface currently presented.
4. Review and enable the applicable security features:
   - **Dependabot alerts**
   - **Secret scanning**
   - **Push protection**, where available
   - **Code scanning / CodeQL**, where required
5. Repeat these steps for **every existing repository** that should be monitored by `github-logs-collector`.

These settings are repository-specific.

Enabling automatic security settings for newly created repositories does not guarantee that older repositories have been updated.

## Why This Is Required

If a security feature is not enabled for a repository, `github-logs-collector` may receive errors when querying the associated GitHub security API.

Typical collector messages include:

```text
Security API request failed repository=<owner>/<repository> type=dependabot error=HTTPError
```

```text
Skipping unavailable security API repository=<owner>/<repository> type=code_scanning status=404
```

```text
Skipping unavailable security API repository=<owner>/<repository> type=secret_scanning status=404
```

These messages do not necessarily indicate a fault in `github-logs-collector`.

They can indicate that the corresponding GitHub security capability is:

- Not enabled
- Not configured
- Not available
- Not licensed
- Not supported for the repository
- Not accessible using the collector credential

## Repository Discovery vs Security API Availability

Repository discovery and security-feature availability are separate.

For example, a log entry such as:

```text
repository=webbie003/github-logs-collector type=dependabot
```

shows that the collector has discovered and is processing the repository.

If the Dependabot query then fails, this does not mean the repository itself is missing from collector scope.

Instead, troubleshoot:

```text
Dependabot feature state
Dependabot alert permissions
Repository eligibility
Token access
```

The same principle applies to code scanning and secret scanning.

## Existing Repository Checklist

For every existing repository that is intended to be monitored:

- [ ] Dependabot alerts enabled
- [ ] Secret scanning enabled, where available
- [ ] Push protection enabled, where available
- [ ] Code scanning / CodeQL enabled or configured, where required
- [ ] Collector credential has permission to read Dependabot alerts
- [ ] Collector credential has permission to read secret scanning alerts
- [ ] Collector credential has permission to read code scanning alerts
- [ ] Repository is included in the collector credential's repository scope
- [ ] Repository appears in `github-logs-collector` polling
- [ ] Collector logs no longer show unexpected security API errors for the repository

## Code Scanning / CodeQL

Enabling access to code scanning alerts does not by itself create code scanning results.

A repository normally also requires a scanning configuration, such as:

- CodeQL default setup
- CodeQL advanced setup
- Another supported scanner uploading SARIF results

If no analysis has been configured, the repository may have no code scanning alerts to collect.

### Recommended CodeQL Configuration

Where appropriate:

1. Open the repository.
2. Select **Settings**.
3. Open **Advanced Security** or **Code security and analysis**.
4. Locate **Code scanning**.
5. Enable **CodeQL default setup**, or configure an appropriate advanced workflow.
6. Confirm the analysis completes successfully.
7. Confirm the collector can query code scanning alerts.

CodeQL configuration requirements vary depending on repository language and project structure.

## Dependabot

Enable Dependabot alerts for repositories that should be monitored for vulnerable dependencies.

If applicable to the repository, also consider:

- Dependabot security updates
- Dependabot version updates

These are separate from the collector's ability to read alert information.

A repository may have Dependabot alerts enabled without Dependabot version updates being configured.

### Recommended Dependabot Settings

Where appropriate:

```text
Dependency graph              Enabled
Dependabot alerts             Enabled
Dependabot security updates   Enabled
Dependabot version updates    Optional / repository-specific
```

## Secret Scanning

Enable secret scanning where available.

Where supported, also enable:

- Push protection
- Additional or generic secret-pattern detection where appropriate

Push protection is preventative.

Secret scanning alerts provide detection and alerting.

Together:

```text
Developer push
      ↓
Push protection
      ↓
Potential secret blocked
      ↓
Secret scanning
      ↓
Detection / alert
      ↓
github-logs-collector
      ↓
Wazuh / SIEM
```

## Collector Credential Permissions

For a fine-grained GitHub personal access token, configure the minimum required repository access and permissions.

Common read permissions for security monitoring include:

```text
Metadata                  Read
Contents                  Read
Dependabot alerts         Read
Code scanning alerts      Read
Secret scanning alerts    Read
```

Use repository access appropriate to the deployment:

- Selected repositories, where practical
- All repositories only when the collector is intentionally intended to monitor all repositories

Do not grant write permissions unless the collector has a documented feature that requires them.

## Repository Access

When creating or updating the fine-grained credential, ensure that newly created repositories are included in its repository access scope.

If the credential is configured for:

```text
Only select repositories
```

a newly created repository may need to be added manually.

If the collector can enumerate a repository through another endpoint but cannot access security APIs, inspect both:

```text
Repository access scope
Security API permissions
```

## Interpreting API Errors

When troubleshooting collector errors, capture the HTTP status code and GitHub response message where possible.

Typical interpretations:

```text
401 -> Authentication failure or invalid credential

403 -> Permission, policy, feature entitlement,
       repository access, rate limit, or token issue

404 -> Endpoint/resource/feature unavailable,
       disabled, inaccessible, or not configured
```

The exact meaning depends on the GitHub API and repository configuration.

The collector should preferably log:

```text
repository
security API type
HTTP status
GitHub response message
```

Example:

```text
Security API request failed repository=example/repository type=dependabot status=403 message="Resource not accessible by personal access token"
```

This is significantly more useful than:

```text
error=HTTPError
```

alone.

## New Repository Validation

Even when automatic settings are enabled for future repositories, verify new repositories after creation.

Suggested validation:

- [ ] Repository is included in collector scope
- [ ] Repository is included in token repository access
- [ ] Dependabot alerts enabled
- [ ] Secret scanning enabled where available
- [ ] Push protection enabled where available
- [ ] Code scanning configured where required
- [ ] Collector can successfully query enabled security APIs
- [ ] No unexplained 403 or 404 security API responses are generated

## `SECURITY.md` Is Separate

A repository containing a `SECURITY.md` file has a published **security policy**.

`SECURITY.md` does **not** enable:

- Dependabot alerts
- Secret scanning
- Push protection
- Code scanning

The security policy and GitHub's automated security-analysis features are separate controls.

The presence of `SECURITY.md` must not be used as an indication that a repository is fully configured for `github-logs-collector` security monitoring.

## Recommended Repository Security Baseline

For repositories where all relevant features are available, the desired state is:

```text
Repository
│
├── SECURITY.md
│   └── Vulnerability reporting policy
│
├── Dependency graph
│
├── Dependabot alerts
│
├── Dependabot security updates
│
├── Secret scanning
│
├── Push protection
│
└── Code scanning / CodeQL
```

The collector then provides central monitoring of supported alert APIs.

## Security Feature Exceptions

Not every GitHub security capability will necessarily be available on every repository.

If a capability cannot be enabled:

1. Confirm the GitHub plan and repository visibility.
2. Confirm repository eligibility.
3. Confirm organization/account policy.
4. Document the exception.
5. Ensure the collector handles the API as unavailable rather than repeatedly treating it as a critical collector failure.

## Collector Verification

After changing GitHub security settings, monitor the collector:

```bash
docker logs -f github-logs-collector
```

Successful queries with no current findings may return an empty result rather than an alert.

Previously observed errors such as:

```text
Skipping unavailable security API repository=<owner>/<repo> type=code_scanning status=404
```

should be investigated again after enabling the corresponding repository feature.

## Credential Rotation

When rotating the collector credential:

- Create the replacement credential with the minimum required permissions.
- Confirm repository access.
- Update the collector secret.
- Restart or recreate the collector as required.
- Verify API connectivity.
- Revoke the previous credential.
- Review logs for authentication or authorization failures.

Never leave replaced credentials active indefinitely.

## Review Frequency

Review repository security settings when:

- A new repository is created
- A repository becomes public or private
- The repository changes ownership or organization
- GitHub introduces or changes security features
- Collector API errors begin appearing
- Collector credentials are rotated or replaced
- A repository begins storing sensitive code or configuration
- A security incident identifies a monitoring gap

## Summary

For reliable security monitoring:

1. Configure appropriate security defaults for future repositories.
2. Review every existing repository separately.
3. Enable the required security features on each repository.
4. Grant the collector only the read permissions it requires.
5. Ensure each monitored repository is in credential scope.
6. Configure CodeQL or another analysis mechanism where code scanning is required.
7. Confirm collector access by reviewing logs after configuration.
8. Treat `SECURITY.md` as a reporting policy, not as an automated security-feature switch.
