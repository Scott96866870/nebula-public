# Changelog

## 0.6.4

- Return every CLI preflight error as a structured JSON object with `ok: false`
  and exit status 2, including overwrite and missing-output-directory checks.
- Add regression coverage for manifest, bundle, and export writer errors.

## 0.6.3

- Reject boolean/floating-point schema versions and file sizes instead of
  interpreting them as integers.
- Reject duplicate JSON fields at all nesting levels and normalize invalid
  UTF-8 manifest errors into the CLI's JSON error response.
- Apply platform-independent canonical relative path validation, preserving
  Unicode filenames and spaces while rejecting ambiguous path syntax.
- Validate Python-constructed manifests, including duplicate paths,
  included/excluded overlaps, empty metadata, and file/directory conflicts.
- Deduplicate repeated build exclusions so generated manifests load cleanly.
- Add manifest parsing, API validation, round-trip, and CLI regression tests.

## 0.6.2

- Stage ZIP, manifest, and release-card outputs beside their destinations;
  preserve the old file on handled failure and clean up temporary output.
- Enforce no-overwrite publication even when another writer creates the output
  concurrently. `--force` replaces the destination atomically after success.
- Stream ZIP entries in 1 MiB chunks and verify the bytes written against the
  supplied manifest before publishing; reject file-set changes after validation.
- Normalize ZIP creator metadata and UTF-8/LF text output across platforms.
- Convert CLI filesystem errors into JSON with exit status 2.
- Add failure, concurrent-destination, streamed-integrity, and reproducibility
  regression tests. Stable source trees are still required during release builds.

## 0.6.1

- Apply manifest exclusions to ZIP contents, so unchecked excluded files are
  not published. Self-excluded manifests are distributed alongside the ZIP.
- Resolve relative CLI manifest output paths from the working directory before
  calculating the manifest's self-exclusion.
- Reject symbolic links, broken links, and Windows junctions/reparse points.
  Share deterministic traversal and prune ignored directories before descent.
- Add regression tests for relative outputs, excluded archive entries,
  reproducibility, ignored paths, symbolic links, and Windows junctions.
- Run CI on Linux and Windows across Python 3.10–3.13.
