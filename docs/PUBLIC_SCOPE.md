# Public Release Scope

This repository is an intentionally limited public distribution. Its purpose
is to make the project's public identity, release metadata, and boundaries
easy to inspect without distributing private or operational source material.

## Included

- Public project overview.
- Static release metadata, rendered as JSON or Markdown.
- A local command that verifies a directory against release exclusions.
- Deterministic SHA-256 manifests and local integrity comparison.
- Manifest-to-manifest diff reports for release review.
- Deterministic ZIP bundle generation after local validation.
- Explicit local export of release cards.
- Unit tests and GitHub Actions checks for catalog, verification, export, and
integrity behavior.

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

When used with `--manifest`, verification also compares the current directory
with a supplied JSON snapshot. The report names missing, modified, and
unexpected paths without printing file contents or hashes.

The `diff` command compares two JSON manifests offline and reports only path
names and release metadata. It does not access the files referenced by either
manifest.

The `bundle` command performs the boundary audit before writing a local ZIP.
It uses normalized ZIP metadata for reproducible output and can require a
matching manifest before packaging. The archive destination itself is not
included when it is inside the source directory.
