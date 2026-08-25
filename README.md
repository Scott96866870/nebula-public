# Nebula Public Edition

Nebula Public Edition is a small, reviewable public overview of the Nebula
project. It provides release metadata and documents the public boundary of
this repository.

## Scope

This edition contains:

- A local, read-only metadata command.
- Public release notes and project-boundary documentation.
- Tests for the metadata command.

This edition intentionally contains no operational networking, traffic
generation, credential or session handling, bypassing, injection, binary
manipulation, or automation functionality. Local configuration, telemetry,
build artifacts, and private project materials are not included.

## Run locally

Requires Python 3.10 or newer.

```text
python -m nebula_public
python main.py info
python main.py catalog
```

## Test

```text
python -m unittest discover -s tests
```

## Repository layout

```text
main.py                 Command-line entry point
nebula_public/          Read-only public metadata package
docs/                   Release scope and maintenance notes
tests/                  Automated checks
```

## Licensing

This public preview is published without a license grant. Contact the project
owner before reusing its contents.
