# Public Release Scope

This repository is an intentionally limited public distribution. Its purpose
is to make the project's public identity, release metadata, and boundaries
easy to inspect without distributing private or operational source material.

## Included

- Public project overview.
- Static release metadata.
- A local command that prints the metadata as JSON.
- Unit tests for the public command.

## Excluded

- Runtime configuration, credentials, telemetry, and user-specific files.
- Build outputs and local development artifacts.
- Operational modules or scripts.
- Private references and internal implementation details.

## Maintenance

Changes to this public edition should remain deterministic and local. Do not
add network clients, file-upload behavior, credential handling, or external
service integrations to this repository without an explicit release review.
