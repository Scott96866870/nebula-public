"""Deterministic local ZIP bundles for the public release."""

from __future__ import annotations

from pathlib import Path
import zipfile

from .audit import IGNORED_DIRECTORIES, audit_public_tree
from .manifest import ReleaseManifest, load_manifest, verify_manifest


FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def _files_for_bundle(root: Path, output: Path) -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in IGNORED_DIRECTORIES for part in relative.parts):
            continue
        if path.is_file() and path.resolve() != output.resolve():
            files.append((relative.as_posix(), path))
    return sorted(files, key=lambda item: item[0])


def create_bundle(
    root: str | Path,
    output: str | Path,
    *,
    manifest: ReleaseManifest | None = None,
) -> tuple[str, ...]:
    """Create a deterministic ZIP archive after validating the public tree.

    The archive contains relative POSIX paths in sorted order. ZIP metadata is
    normalized so repeated builds from unchanged input produce identical bytes.
    """
    base = Path(root).resolve()
    destination = Path(output).expanduser().resolve()
    if not base.is_dir():
        raise ValueError(f"Bundle path is not a directory: {base}")
    if not destination.parent.is_dir():
        raise ValueError(f"Output directory does not exist: {destination.parent}")

    boundary = audit_public_tree(base)
    if not boundary.ok:
        paths = ", ".join(item.path for item in boundary.violations)
        raise ValueError(f"Public boundary check failed: {paths}")
    if manifest is not None:
        integrity = verify_manifest(base, manifest, exclude=(destination,))
        if not integrity.ok:
            details = ", ".join(
                f"{label}={len(values)}"
                for label, values in (
                    ("missing", integrity.missing),
                    ("modified", integrity.modified),
                    ("unexpected", integrity.unexpected),
                )
                if values
            )
            raise ValueError(f"Manifest integrity check failed: {details}")

    files = _files_for_bundle(base, destination)
    try:
        with zipfile.ZipFile(
            destination, mode="w", compression=zipfile.ZIP_STORED
        ) as archive:
            for relative, path in files:
                info = zipfile.ZipInfo(relative, date_time=FIXED_ZIP_TIMESTAMP)
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())
    except OSError as error:
        raise ValueError(f"Unable to write bundle: {destination}") from error
    return tuple(relative for relative, _ in files)


def create_bundle_from_manifest(
    root: str | Path, output: str | Path, manifest_path: str | Path
) -> tuple[str, ...]:
    """Load a manifest and create a bundle with integrity verification."""
    return create_bundle(root, output, manifest=load_manifest(manifest_path))
