# Changelog

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
