# GitHub Logs Collector

A Docker-based collector for retrieving GitHub account, repository, audit/security, Dependabot, code scanning, and secret scanning events and forwarding them into a central logging/SIEM workflow.

## Purpose

`github-logs-collector` is intended to provide central visibility of GitHub activity and repository security events.

Typical use cases include:

- Repository activity monitoring
- GitHub security event collection
- Dependabot alert monitoring
- Code scanning alert monitoring
- Secret scanning alert monitoring
- Centralised logging into Wazuh or another SIEM
- Security investigation and historical review

## Security Model

The collector should use a dedicated GitHub credential with only the permissions required for the configured monitoring functions.

Do not place GitHub credentials directly in source files or commit them to the repository.

Use environment variables, Docker secrets, or another protected secret-management mechanism.

## GitHub Repository Security Features

The collector can only retrieve security alerts for features that are enabled and available for the repository.

The following features should be considered for repositories that are to be monitored:

- Dependabot alerts
- Secret scanning
- Push protection
- Code scanning / CodeQL

### Existing repositories

Enabling security features for future repositories does not guarantee that they are enabled on repositories that already exist.

**Each existing repository that should be monitored must be reviewed individually.**

For each existing repository:

1. Open the repository in GitHub.
2. Select **Settings**.
3. Open **Advanced Security** or **Code security and analysis**, depending on the GitHub interface.
4. Enable the required features where available:
   - Dependabot alerts
   - Secret scanning
   - Push protection
   - Code scanning / CodeQL
5. Repeat for every existing repository that should be monitored.

For full setup guidance, see [GITHUB_SECURITY_SETUP.md](GITHUB_SECURITY_SETUP.md).

## SECURITY.md

A `SECURITY.md` file publishes the repository's vulnerability-reporting policy.

It does **not** enable:

- Dependabot alerts
- Secret scanning
- Push protection
- Code scanning

These GitHub security features are configured separately.

## Typical Collector Messages

If a repository security feature is disabled or unavailable, the collector may record messages similar to:

```text
Security API request failed repository=<owner>/<repo> type=dependabot error=HTTPError
```

```text
Skipping unavailable security API repository=<owner>/<repo> type=code_scanning status=404
```

```text
Skipping unavailable security API repository=<owner>/<repo> type=secret_scanning status=404
```

These messages do not automatically mean the collector itself is faulty.

Confirm the repository feature state and collector credential permissions first.

A repository can be successfully discovered and enumerated by the collector while one or more security APIs remain unavailable.

For example:

```text
repository=webbie003/github-logs-collector type=dependabot
```

confirms that the repository is being processed by the collector.

A subsequent Dependabot, code scanning, or secret scanning API error relates to the availability of that particular security service rather than repository discovery.

## Recommended GitHub Credential Permissions

For a fine-grained GitHub personal access token, use only the permissions required by your deployment.

Common read permissions include:

```text
Metadata                  Read
Contents                  Read
Dependabot alerts         Read
Code scanning alerts      Read
Secret scanning alerts    Read
```

Repository access should include only the repositories that the collector is intended to monitor, unless monitoring all repositories is an explicit requirement.

Do not grant write access unless a documented collector function requires it.

## Collector Error Logging

Security API errors should include the HTTP status code where possible.

Preferred logging:

```text
Security API request failed repository=<owner>/<repo> type=dependabot status=403 message="Resource not accessible by personal access token"
```

rather than only:

```text
Security API request failed repository=<owner>/<repo> type=dependabot error=HTTPError
```

Capturing the HTTP response status makes troubleshooting significantly easier.

Typical interpretations include:

```text
401  Authentication failed or invalid credential
403  Permission, policy, feature access, or rate-limit issue
404  Resource or security feature unavailable/not enabled
```

The exact meaning depends on the GitHub API being queried.

## Docker Security

Recommended container controls include:

- Run with the minimum required privileges
- `no-new-privileges:true`
- Do not mount the Docker socket unless strictly required
- Set CPU, memory, and PID limits where practical
- Keep secrets outside the image and source repository
- Use a dedicated Docker network where practical
- Keep the image and dependencies patched
- Prefer pinned image versions or digests for production deployments
- Restrict filesystem write access where practical
- Avoid unnecessary Linux capabilities
- Protect collector logs because they may contain repository or security-event metadata

## Credential Security

Never commit the following to Git:

```text
GitHub personal access tokens
GitHub App private keys
API keys
Passwords
Webhook secrets
Session tokens
Private certificates or signing keys
```

If a credential is accidentally committed:

1. Revoke or rotate it immediately.
2. Remove it from the repository.
3. Review repository history and logs for exposure.
4. Review GitHub audit/security activity.
5. Replace the credential in the collector deployment.

Deleting a secret from the latest commit alone does not make a previously exposed credential safe.

## Security Feature Availability

Security functionality may vary depending on:

- Repository visibility
- GitHub plan
- Repository ownership
- Organization policy
- GitHub Advanced Security availability
- Security feature configuration
- Token permissions
- Repository eligibility

The collector should therefore treat unavailable security APIs gracefully.

An unavailable API for one repository should not prevent monitoring of other repositories.

## Code Scanning

Code scanning requires an analysis mechanism before useful alerts will exist.

Common options include:

- CodeQL default setup
- CodeQL advanced setup
- Third-party tools that upload SARIF results

Simply granting the collector permission to read code scanning alerts does not configure CodeQL.

## Dependabot

Dependabot alerts should be enabled for repositories where vulnerable dependency monitoring is required.

Additional controls may include:

- Dependabot security updates
- Dependabot version updates

These are separate features from the collector's ability to retrieve Dependabot alerts.

## Secret Scanning

Secret scanning should be enabled where available.

Push protection should also be enabled where practical to help prevent recognised secrets from being committed in the first place.

Secret scanning and push protection complement each other:

```text
Push protection
    ↓
Prevent secret introduction

Secret scanning
    ↓
Detect exposed secrets

github-logs-collector
    ↓
Centralise alert visibility
```

## Existing Repository Requirement

Existing repositories must be checked individually.

Configuring GitHub to automatically enable security features on new repositories does not guarantee that those same settings have been applied retrospectively to existing repositories.

For each existing monitored repository, confirm:

```text
Dependabot alerts
Secret scanning
Push protection
Code scanning / CodeQL
Collector API permissions
```

See [GITHUB_SECURITY_SETUP.md](GITHUB_SECURITY_SETUP.md) for the full checklist.

## Documentation

- [GITHUB_SECURITY_SETUP.md](GITHUB_SECURITY_SETUP.md) — GitHub security configuration required for monitoring
- [SECURITY.md](SECURITY.md) — vulnerability reporting policy
- [CHANGELOG.md](CHANGELOG.md) — project and documentation changes

## Important

Security functionality and availability can vary by repository visibility, GitHub plan, repository configuration, and GitHub feature eligibility.

Always verify the effective settings on each monitored repository.
