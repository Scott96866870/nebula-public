# Public Release Scope

This repository is an intentionally limited public distribution. Its purpose
is to make the project's public identity, release metadata, and boundaries
easy to inspect without distributing private or operational source material.

## Included

- Public project overview.
- Static release metadata, rendered as JSON or Markdown.
- A local command that verifies a directory against release exclusions.
- Explicit local export of release cards.
- Unit tests for catalog, verification, and export behavior.

## Excluded

- Runtime configuration, credentials, telemetry, and user-specific files.
- Build outputs and local development artifacts.
- Operational modules or scripts.
- Private references and internal implementation details.

## Maintenance

Changes to this public edition should remain deterministic and local. Do not
add network clients, file-upload behavior, credential handling, or external
service integrations to this repository without an explicit release review.

The `verify` command checks for local configuration, telemetry, credentials,
private keys, and build directories. It reports relative paths and rule names,
not file contents.
