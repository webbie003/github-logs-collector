# Changelog

All notable changes to `github-logs-collector` documentation and deployment guidance will be documented in this file.

The format is based on Keep a Changelog principles, with changes grouped by release or documentation update.

## [Unreleased]

### Added

- Added `GITHUB_SECURITY_SETUP.md` with guidance for configuring GitHub repository security features used by `github-logs-collector`.
- Added explicit instructions for existing repositories:
  - Dependabot alerts must be enabled individually where required.
  - Secret scanning must be enabled individually where available.
  - Push protection should be enabled individually where available.
  - Code scanning / CodeQL must be enabled or configured individually where required.
- Added clarification that account-level or organization-level defaults for future repositories do not necessarily apply retrospectively to existing repositories.
- Added an existing-repository validation checklist.
- Added guidance for fine-grained GitHub credential permissions:
  - Metadata: Read
  - Contents: Read
  - Dependabot alerts: Read
  - Code scanning alerts: Read
  - Secret scanning alerts: Read
- Added troubleshooting guidance for common GitHub API responses including HTTP 401, 403, and 404.
- Added clarification that a repository `SECURITY.md` file defines a vulnerability-reporting policy only and does not enable Dependabot, secret scanning, push protection, or code scanning.
- Added recommendation to capture the GitHub API HTTP status and response message when logging security API failures.
- Added guidance for validating new repositories even when future-repository security defaults are enabled.

### Changed

- Updated `README.md` to link repository security monitoring requirements to `GITHUB_SECURITY_SETUP.md`.
- Updated documentation to distinguish repository discovery from security-feature availability.
- Updated security guidance to recommend least-privilege access for the collector credential.
- Updated Docker security recommendations to retain `no-new-privileges:true`, avoid unnecessary Docker socket access, apply resource limits, and protect secrets outside the image and source repository.
- Updated repository monitoring guidance to state that a repository may be enumerated successfully by the collector while individual security APIs remain unavailable because the relevant GitHub feature is disabled or inaccessible.

### Security

- Documented that GitHub credentials, API keys, private keys, webhook secrets, session tokens, and discovered secrets must not be committed to the repository or included in public logs.
- Documented that exposed credentials should be revoked or rotated immediately.
- Clarified that repository security features and the repository security policy are separate controls.

## Initial Documentation Set

### Refreshed

- `README.md`
- `GITHUB_SECURITY_SETUP.md`
- `SECURITY.md`
- `CHANGELOG.md`

