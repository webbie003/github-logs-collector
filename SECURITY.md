# Security Policy

## Reporting a Vulnerability

Please do not publicly disclose a suspected security vulnerability before it has been reviewed.

If you identify a vulnerability in `github-logs-collector`, report it privately through the repository's GitHub security reporting capability when available.

Include enough information to reproduce and assess the issue, such as:

- Affected component or file
- Affected version or commit
- Description of the vulnerability
- Reproduction steps
- Expected and actual behaviour
- Potential security impact
- Relevant logs or screenshots with secrets removed
- Suggested remediation, if known

## Sensitive Information

Do not include any of the following in public issues, pull requests, screenshots, or logs:

- GitHub personal access tokens
- API keys
- Passwords
- Private keys
- Session tokens
- Webhook secrets
- Internal credentials
- Unredacted secrets discovered by the collector

If sensitive credentials are exposed, revoke or rotate them immediately.

## Supported Versions

Security fixes are expected to target the current maintained version of the project.

Older revisions may not receive security updates.

## Security Design

The project should follow least-privilege principles.

Recommended deployment controls include:

- Dedicated GitHub credentials for the collector
- Read-only GitHub permissions wherever possible
- Protected environment variables or secret storage
- Container privilege reduction
- `no-new-privileges:true`
- Resource limits
- Restricted Docker networking where practical
- No Docker socket access unless explicitly required
- Regular dependency and image updates
- GitHub repository security features enabled where available

## GitHub Credential Permissions

The GitHub credential used by the collector should be limited to the repositories and APIs that it needs.

Common read-only permissions include:

```text
Metadata                  Read
Contents                  Read
Dependabot alerts         Read
Code scanning alerts      Read
Secret scanning alerts    Read
```

Do not assign write or administrative permissions unless a documented application feature explicitly requires them.

## Credential Storage

GitHub credentials must not be embedded directly in:

```text
Python source files
Dockerfiles
docker-compose.yml
README files
Shell scripts
Git-tracked environment files
```

Use an appropriate secret mechanism such as:

- Protected environment variables
- Docker secrets
- Host-side protected secret files
- A dedicated secrets-management platform

Ensure secret files are excluded from Git.

For example:

```gitignore
.env
*.key
*.pem
secrets/
```

Adjust exclusions to the project's actual structure.

## Logging

Logs should provide enough information for troubleshooting without exposing sensitive credentials.

Safe metadata may include:

```text
Repository name
Security API type
HTTP response status
Event identifier
Collector processing state
```

Avoid logging:

```text
Authorization headers
Personal access tokens
Private keys
Session secrets
Webhook secrets
Raw credentials
```

When GitHub API requests fail, log the HTTP status and safe response message where possible.

## Container Security

The collector container should operate with minimal privileges.

Recommended controls include:

```yaml
security_opt:
  - no-new-privileges:true
```

Where compatible with the application, also consider:

- Read-only filesystems
- Dropped Linux capabilities
- Memory limits
- PID limits
- CPU limits
- Non-root execution
- Restricted bind mounts
- Dedicated Docker networks

Do not apply controls blindly if they prevent required functionality.

Each hardening control should be validated against the running application.

## Docker Socket

Do not mount:

```text
/var/run/docker.sock
```

into the collector unless there is an explicit and unavoidable functional requirement.

Access to the Docker daemon can provide extensive control over containers and potentially the host.

## Dependency Security

Keep application dependencies current.

Repository security controls should include, where available:

- Dependency graph
- Dependabot alerts
- Dependabot security updates
- Code scanning
- Secret scanning
- Push protection

Security updates should be reviewed before deployment.

## GitHub Security Features

This `SECURITY.md` file defines the project's vulnerability-reporting policy.

It does **not** enable GitHub security products such as:

- Dependabot alerts
- Secret scanning
- Push protection
- Code scanning / CodeQL

Those features must be configured separately in GitHub repository security settings.

Existing repositories may require these controls to be enabled individually.

See [GITHUB_SECURITY_SETUP.md](GITHUB_SECURITY_SETUP.md) for repository monitoring configuration.

## Secret Scanning

Secret scanning should be enabled for the repository where available.

Push protection should also be enabled where available to reduce the likelihood of credentials being introduced into repository history.

If a secret is discovered:

1. Revoke or rotate the credential immediately.
2. Determine when it was exposed.
3. Determine where it was used.
4. Review relevant audit and access logs.
5. Remove the secret from active source/configuration.
6. Consider repository history cleanup where appropriate.
7. Do not assume history rewriting makes the credential safe.

Credential rotation is the primary containment action.

## Security Updates

Security-related changes should be documented in `CHANGELOG.md` where appropriate.

Do not place exploit details in the changelog before users have had reasonable opportunity to apply a security fix.

## Vulnerability Disclosure

Where a vulnerability affects users of the project, coordinated disclosure is preferred.

A security report should include:

```text
Affected versions
Fixed versions
Impact
Mitigation
Upgrade guidance
```

Sensitive exploit details may be withheld until remediation is available.

## Scope

This policy covers security issues in the `github-logs-collector` project itself.

Alerts retrieved by the collector from monitored repositories are findings relating to those repositories and should be handled according to the applicable repository or organization's incident-response process.
