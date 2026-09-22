# Nebula Public Edition

Nebula Public Edition is a local Python toolkit for release manifests,
integrity checks, release reports, and reproducible ZIP bundles.

Current version: **0.6.2**. See [release notes](docs/CHANGELOG.md).

## Scope

This edition contains:

- A local release catalog in JSON or Markdown.
- A deterministic public-boundary verifier for local directories.
- Reproducible SHA-256 manifests and integrity verification.
- Manifest-to-manifest diff reports for release review.
- Deterministic ZIP bundle generation for a public release.
- Aggregated release-readiness reports with file statistics.
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
python main.py manifest --output release-manifest.json
python main.py verify --manifest release-manifest.json
python main.py diff previous-manifest.json release-manifest.json
python main.py diff previous-manifest.json release-manifest.json --format markdown
python main.py bundle --output nebula-public.zip
python main.py bundle --output nebula-public.zip --manifest release-manifest.json
python main.py report
python main.py report --manifest release-manifest.json --format markdown
```

`verify` returns status code `0` when the target contains no excluded files,
and `1` when it finds a blocked path. It never sends data or connects to an
external service. `export` writes only to the explicitly supplied local path
and will not replace an existing file unless `--force` is used.

`export`, `manifest --output`, and `bundle` stage output beside the destination
and publish it only after a successful write. A handled write failure preserves
the previous destination and removes the temporary file. Without `--force`,
publication uses an exclusive hard link to avoid overwriting a file created
by another process; this requires a filesystem with hard-link support (such
as NTFS, ext4, or APFS). `--force` uses atomic replacement. Output links and
non-regular destinations are rejected. I/O errors return status `2` and a JSON
error instead of a traceback. Text outputs use UTF-8 with LF line endings.

## Integrity manifests

`manifest` creates a deterministic JSON snapshot of every included file. Each
entry records a relative path, byte size, and SHA-256 digest; it does not add a
timestamp or upload anything. When the destination is inside the inspected
directory, the manifest automatically excludes itself.
Relative CLI output paths are interpreted from the current working directory,
including when `--path` selects a different source directory.

Use `verify --manifest release-manifest.json` before sharing an archive or
cutting a release. In addition to the public-boundary audit, it reports files
that are missing, modified, or unexpectedly present.

`diff` compares two manifests without reading the underlying source tree. It
reports added, removed, modified, and unchanged relative paths and can render
the result as JSON or Markdown for a changelog.

`bundle` validates the public boundary before creating a ZIP archive. Entries
are sorted and use normalized timestamps and permissions, so repeated builds
from unchanged input produce identical archive bytes. Existing destinations
are protected unless `--force` is supplied. Add `--manifest` to require an
integrity match before packaging.
With `--manifest`, the ZIP also omits every path listed in the manifest's
`excluded_paths`, including the manifest itself when generated inside the tree.
Distribute that manifest alongside the ZIP when needed.

Filesystem symbolic links, broken links, and Windows junctions/reparse points
inside the source tree are rejected. The scanner never descends into them.
Use regular files and directories in a stable source tree while building;
validation and packaging are not an atomic filesystem snapshot.

ZIP entries are copied in 1 MiB chunks, so large files are not loaded into
memory at once. When `--manifest` is supplied, the size and SHA-256 digest of
the bytes actually written to each entry are checked again before publishing.
A mismatch leaves the previous ZIP intact. ZIP creator metadata is normalized
across operating systems; archive bytes may differ from 0.6.1 even with the same
inputs. At the Python API level, `create_bundle(..., overwrite=False)` enables
exclusive publication; the default remains `True` for compatibility.

`report` combines the boundary audit, optional manifest integrity check,
version alignment, file count, byte total, extension summary, and actionable
recommendations. It is designed for a final offline release review and can be
rendered as JSON or Markdown.

The repository's GitHub Actions workflow runs the unit test suite on every
push to `main` and pull request, on Linux and Windows with Python 3.10–3.13.

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
