# Security Policy

Security is a primary design goal of GitHub Logs Collector.

The project receives externally supplied webhook traffic and should therefore
be treated as an internet-facing security-sensitive service.

## Supported Versions

Security updates are provided for the latest released version.

| Version | Supported |
|---|---|
| 0.1.x | Yes |

## Reporting a Vulnerability

Do not disclose suspected security vulnerabilities through a public GitHub
issue.

Use GitHub Private Vulnerability Reporting where available.

Reports should include:

- affected version
- vulnerability description
- reproduction steps
- security impact
- suggested mitigation, if known

Please avoid including real webhook secrets, access tokens, credentials, or
other sensitive production information.

## Security Architecture

The collector implements multiple defensive controls.

### Webhook Authentication

GitHub webhook requests are authenticated using the
`X-Hub-Signature-256` header.

The collector:

1. reads the original HTTP request body
2. calculates an HMAC-SHA256 digest using the configured webhook secret
3. performs constant-time comparison using `hmac.compare_digest()`
4. rejects requests whose signatures do not match

Unsigned or incorrectly signed requests are not processed or written to the
event log.

### Secret Management

The GitHub webhook secret must not be:

- embedded in source code
- committed to Git
- included in container images
- written to application logs

Generate secrets using a cryptographically secure source, for example:

    openssl rand -hex 32

Production deployments should preferably use a dedicated secret-management
solution.

### Request Validation

The collector:

- accepts only JSON webhook requests
- limits maximum request-body size
- validates GitHub event metadata
- limits metadata field lengths
- rejects malformed JSON payloads

### Logging

The collector does not intentionally log:

- GitHub webhook secrets
- X-Hub-Signature-256 values
- Authorization headers
- Cookie headers
- arbitrary HTTP request headers

GitHub event payloads may themselves contain sensitive repository or account
information.

Administrators are responsible for securing access to collected event logs.

### Container Security

The recommended Docker deployment uses:

- non-root execution
- dedicated UID/GID
- `no-new-privileges`
- all Linux capabilities dropped
- read-only root filesystem
- limited writable filesystem locations
- memory-backed `/tmp`
- process limits
- CPU limits
- memory limits
- log rotation
- no interactive stdin
- no pseudo-terminal

### Network Security

The collector defaults to binding Docker's published port to:

    127.0.0.1

For internet-facing deployments, TLS should terminate at a trusted reverse
proxy or ingress service.

Recommended architecture:

    Internet
        |
       TLS
        |
    Reverse Proxy
        |
    Private Network
        |
    GitHub Logs Collector

Do not expose Flask's development server directly to the Internet.

### SIEM Access

Where a SIEM consumes the collector output using a shared Docker volume,
the SIEM should receive read-only access whenever possible.

Example:

    github_logs:/var/log/github:ro

### Dependency Security

Direct Python dependencies are version-pinned for reproducible builds.

Container and dependency vulnerability scanning should be performed before
publishing a release.

Future releases may additionally use dependency hashes and pinned base-image
digests for stronger supply-chain integrity.

### Health Endpoint

The health endpoint intentionally provides only minimal operational state.

It must not expose:

- secrets
- environment variables
- package versions
- filesystem paths
- internal configuration
- stack traces

### Known Design Considerations

The collector preserves the original GitHub webhook JSON payload for SIEM
analysis.

This provides maximum detection and investigation value but means collected
events may contain sensitive repository metadata.

Log storage and SIEM access controls should therefore be treated as
security-sensitive.

Webhook delivery IDs are retained for correlation.

The initial collector does not perform automatic replay suppression because
legitimate GitHub webhook redelivery may be operationally useful to SIEM
platforms.
