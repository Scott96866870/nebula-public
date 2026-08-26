# Nebula Public Edition

Nebula Public Edition is a small, reviewable public overview of the Nebula
project. It provides release metadata and documents the public boundary of
this repository.

## Scope

This edition contains:

- A local release catalog in JSON or Markdown.
- A deterministic public-boundary verifier for local directories.
- Local export support for release cards.
- Public release notes, scope documentation, and tests.

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
python main.py catalog --format markdown
python main.py verify
python main.py export --output release-card.md
```

`verify` returns status code `0` when the target contains no excluded files,
and `1` when it finds a blocked path. It never sends data or connects to an
external service. `export` writes only to the explicitly supplied local path
and will not replace an existing file unless `--force` is used.

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
