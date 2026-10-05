"""Deterministic local release manifests and integrity verification."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable

from .tree import public_paths, require_regular_path
from .catalog import release


MANIFEST_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ManifestEntry:
    """One file captured by a release manifest."""

    path: str
    size: int
    sha256: str

    def to_dict(self) -> dict[str, object]:
        return {"path": self.path, "sha256": self.sha256, "size": self.size}


@dataclass(frozen=True)
class ReleaseManifest:
    """A portable, deterministic snapshot of a public release tree."""

    schema_version: int
    release_name: str
    release_version: str
    entries: tuple[ManifestEntry, ...]
    excluded_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_manifest(self)

    def to_dict(self) -> dict[str, object]:
        return {
            "excluded_paths": list(self.excluded_paths),
            "files": [entry.to_dict() for entry in self.entries],
            "release": {"name": self.release_name, "version": self.release_version},
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        """Return canonical JSON suitable for review or source control."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class IntegrityReport:
    """Comparison between a manifest and the current local tree."""

    root: str
    expected_files: int
    actual_files: int
    missing: tuple[str, ...]
    modified: tuple[str, ...]
    unexpected: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not (self.missing or self.modified or self.unexpected)

    def to_dict(self) -> dict[str, object]:
        return {
            "actual_files": self.actual_files,
            "expected_files": self.expected_files,
            "missing": list(self.missing),
            "modified": list(self.modified),
            "ok": self.ok,
            "root": self.root,
            "unexpected": list(self.unexpected),
        }


@dataclass(frozen=True)
class ManifestDiff:
    """File, release metadata, and exclusion changes between manifests."""

    left_release: str
    right_release: str
    added: tuple[str, ...]
    removed: tuple[str, ...]
    modified: tuple[str, ...]
    unchanged: tuple[str, ...]
    metadata_changed: bool = False
    exclusions_added: tuple[str, ...] = ()
    exclusions_removed: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(
            self.added or self.removed or self.modified or self.metadata_changed
            or self.exclusions_added or self.exclusions_removed
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "added": list(self.added),
            "changed": self.changed,
            "metadata_changed": self.metadata_changed,
            "exclusions_added": list(self.exclusions_added),
            "exclusions_removed": list(self.exclusions_removed),
            "left_release": self.left_release,
            "modified": list(self.modified),
            "removed": list(self.removed),
            "right_release": self.right_release,
            "unchanged": list(self.unchanged),
        }

    def to_markdown(self) -> str:
        """Render a concise release comparison for a changelog or review."""
        lines = [
            f"# Manifest diff: {self.left_release} -> {self.right_release}",
            "",
            f"**Changed:** {'yes' if self.changed else 'no'}",
            f"**Release metadata changed:** {'yes' if self.metadata_changed else 'no'}",
            "",
        ]
        for heading, values in (
            ("Added", self.added),
            ("Removed", self.removed),
            ("Modified", self.modified),
            ("Unchanged", self.unchanged),
            ("Exclusions added", self.exclusions_added),
            ("Exclusions removed", self.exclusions_removed),
        ):
            lines.extend([f"## {heading}", ""])
            lines.extend(f"- {value}" for value in values)
            if not values:
                lines.append("- None")
            lines.append("")
        return "\n".join(lines)


def _file_digest(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_path(base: Path, candidate: Path) -> str | None:
    try:
        resolved = candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve()
        return resolved.relative_to(base).as_posix()
    except ValueError:
        return None


def _manifest_entries(base: Path, excluded_paths: set[str]) -> tuple[ManifestEntry, ...]:
    entries: list[ManifestEntry] = []
    for path in public_paths(base):
        relative = path.relative_to(base)
        require_regular_path(path, base)
        if not path.is_file() or relative.as_posix() in excluded_paths:
            continue
        entries.append(
            ManifestEntry(
                path=relative.as_posix(),
                size=path.stat().st_size,
                sha256=_file_digest(path),
            )
        )
    return tuple(sorted(entries, key=lambda entry: entry.path))


def build_manifest(
    root: str | Path, *, exclude: Iterable[str | Path] = ()
) -> ReleaseManifest:
    """Build a release manifest from a local directory without network access."""
    base = Path(root).resolve()
    if not base.is_dir():
        raise ValueError(f"Manifest path is not a directory: {base}")

    excluded_paths = sorted({
        relative
        for item in exclude
        if (relative := _relative_path(base, Path(item))) is not None
    })
    return ReleaseManifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        release_name=release.name,
        release_version=release.version,
        entries=_manifest_entries(base, set(excluded_paths)),
        excluded_paths=tuple(excluded_paths),
    )


def load_manifest(path: str | Path) -> ReleaseManifest:
    """Load and validate a JSON release manifest from disk."""
    source = Path(path).expanduser()
    try:
        data = json.loads(
            source.read_text(encoding="utf-8"), object_pairs_hook=_unique_json_object
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Unable to read manifest: {source}") from error

    if (
        not isinstance(data, dict)
        or type(data.get("schema_version")) is not int
        or data["schema_version"] != MANIFEST_SCHEMA_VERSION
    ):
        raise ValueError("Unsupported or invalid manifest schema")
    release_data = data.get("release")
    file_data = data.get("files")
    excluded_data = data.get("excluded_paths", [])
    if (
        not isinstance(release_data, dict)
        or not isinstance(release_data.get("name"), str)
        or not isinstance(release_data.get("version"), str)
        or not isinstance(file_data, list)
        or not isinstance(excluded_data, list)
    ):
        raise ValueError("Manifest is missing required fields")

    excluded_paths = _validate_relative_paths(excluded_data, "excluded path")
    entries: list[ManifestEntry] = []
    for item in file_data:
        if not isinstance(item, dict):
            raise ValueError("Manifest file entry must be an object")
        entry_path = item.get("path")
        entry_size = item.get("size")
        entry_digest = item.get("sha256")
        if (
            not isinstance(entry_path, str)
            or type(entry_size) is not int
            or entry_size < 0
            or not isinstance(entry_digest, str)
            or len(entry_digest) != 64
            or any(char not in "0123456789abcdef" for char in entry_digest)
        ):
            raise ValueError("Manifest contains an invalid file entry")
        _validate_relative_paths([entry_path], "file path")
        entries.append(ManifestEntry(entry_path, entry_size, entry_digest))

    if len({entry.path for entry in entries}) != len(entries):
        raise ValueError("Manifest contains duplicate file paths")
    return ReleaseManifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        release_name=release_data["name"],
        release_version=release_data["version"],
        entries=tuple(sorted(entries, key=lambda entry: entry.path)),
        excluded_paths=tuple(excluded_paths),
    )


def _validate_relative_paths(values: list[object], label: str) -> list[str]:
    paths: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError(f"Manifest {label} must be a string")
        candidate = PurePosixPath(value)
        if (
            not value or value == "." or candidate.is_absolute()
            or PureWindowsPath(value).drive or "\\" in value or ":" in value
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
            or ".." in candidate.parts or value != candidate.as_posix()
        ):
            raise ValueError(f"Manifest {label} must be a relative POSIX path")
        paths.append(value)
    if len(set(paths)) != len(paths):
        raise ValueError(f"Manifest contains duplicate {label}s")
    folded = [path.casefold() for path in paths]
    if len(set(folded)) != len(folded):
        raise ValueError(f"Manifest contains case-insensitive duplicate {label}s")
    return sorted(paths)


def _folded_path(path: str) -> str:
    return "/".join(part.casefold() for part in PurePosixPath(path).parts)


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Manifest contains duplicate JSON field: {key}")
        result[key] = value
    return result


def _validate_manifest(manifest: ReleaseManifest) -> None:
    if type(manifest.schema_version) is not int or manifest.schema_version != MANIFEST_SCHEMA_VERSION:
        raise ValueError("Unsupported or invalid manifest schema")
    if any(not isinstance(value, str) or not value.strip()
           for value in (manifest.release_name, manifest.release_version)):
        raise ValueError("Manifest release name and version must be non-empty strings")
    if not isinstance(manifest.entries, tuple) or not isinstance(manifest.excluded_paths, tuple):
        raise ValueError("Manifest entries and exclusions must be immutable tuples")
    paths: list[object] = []
    for entry in manifest.entries:
        if (
            not isinstance(entry, ManifestEntry)
            or type(entry.size) is not int or entry.size < 0
            or not isinstance(entry.sha256, str) or len(entry.sha256) != 64
            or any(char not in "0123456789abcdef" for char in entry.sha256)
        ):
            raise ValueError("Manifest contains an invalid file entry")
        paths.append(entry.path)
    included = set(_validate_relative_paths(paths, "file path"))
    excluded = set(_validate_relative_paths(list(manifest.excluded_paths), "excluded path"))
    folded_included = {_folded_path(path) for path in included}
    folded_excluded = {_folded_path(path) for path in excluded}
    if folded_included & folded_excluded:
        raise ValueError("Manifest file paths overlap excluded paths")
    for path in included:
        folded_parents = {
            _folded_path(parent.as_posix()) for parent in PurePosixPath(path).parents
        }
        if folded_parents & folded_included:
            raise ValueError("Manifest file paths contain a file/directory conflict")


def verify_manifest(
    root: str | Path,
    manifest: ReleaseManifest,
    *,
    exclude: Iterable[str | Path] = (),
) -> IntegrityReport:
    """Compare a local tree with a previously generated release manifest."""
    base = Path(root).resolve()
    if not base.is_dir():
        raise ValueError(f"Manifest path is not a directory: {base}")

    excluded_paths = set(manifest.excluded_paths)
    for item in exclude:
        if (relative := _relative_path(base, Path(item))) is not None:
            excluded_paths.add(relative)
    actual = {entry.path: entry for entry in _manifest_entries(base, excluded_paths)}
    expected = {entry.path: entry for entry in manifest.entries}
    missing = tuple(sorted(expected.keys() - actual.keys()))
    unexpected = tuple(sorted(actual.keys() - expected.keys()))
    modified = tuple(
        sorted(
            path
            for path in expected.keys() & actual.keys()
            if expected[path] != actual[path]
        )
    )
    return IntegrityReport(
        root=str(base),
        expected_files=len(expected),
        actual_files=len(actual),
        missing=missing,
        modified=modified,
        unexpected=unexpected,
    )


def compare_manifests(left: ReleaseManifest, right: ReleaseManifest) -> ManifestDiff:
    """Compare two manifests without reading files from disk."""
    left_entries = {entry.path: entry for entry in left.entries}
    right_entries = {entry.path: entry for entry in right.entries}
    shared = left_entries.keys() & right_entries.keys()
    return ManifestDiff(
        left_release=f"{left.release_name} {left.release_version}",
        right_release=f"{right.release_name} {right.release_version}",
        added=tuple(sorted(right_entries.keys() - left_entries.keys())),
        removed=tuple(sorted(left_entries.keys() - right_entries.keys())),
        modified=tuple(
            sorted(path for path in shared if left_entries[path] != right_entries[path])
        ),
        unchanged=tuple(
            sorted(path for path in shared if left_entries[path] == right_entries[path])
        ),
        metadata_changed=(
            (left.release_name, left.release_version)
            != (right.release_name, right.release_version)
        ),
        exclusions_added=tuple(sorted(set(right.excluded_paths) - set(left.excluded_paths))),
        exclusions_removed=tuple(sorted(set(left.excluded_paths) - set(right.excluded_paths))),
    )
