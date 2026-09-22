"""Deterministic local ZIP bundles for the public release."""

from __future__ import annotations

from pathlib import Path
from hashlib import sha256
import zipfile

from .audit import audit_public_tree
from .manifest import ReleaseManifest, load_manifest, verify_manifest
from .tree import public_paths, require_regular_path
from .output import atomic_output, output_path


FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
COPY_CHUNK_SIZE = 1024 * 1024


def _files_for_bundle(
    root: Path, output: Path, excluded_paths: tuple[str, ...] = ()
) -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    excluded = set(excluded_paths)
    for path in public_paths(root):
        relative = path.relative_to(root)
        require_regular_path(path, root)
        if relative.as_posix() in excluded:
            continue
        if path.is_file() and path.resolve() != output.resolve():
            files.append((relative.as_posix(), path))
    return sorted(files, key=lambda item: item[0])


def create_bundle(
    root: str | Path,
    output: str | Path,
    *,
    manifest: ReleaseManifest | None = None,
    overwrite: bool = True,
) -> tuple[str, ...]:
    """Create a deterministic ZIP archive after validating the public tree.

    The archive contains relative POSIX paths in sorted order. ZIP metadata is
    normalized so repeated builds from unchanged input produce identical bytes.
    """
    base = Path(root).resolve()
    destination = output_path(output)
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

    files = _files_for_bundle(
        base, destination, manifest.excluded_paths if manifest is not None else ()
    )
    expected = {entry.path: entry for entry in manifest.entries} if manifest is not None else None
    if expected is not None and set(expected) != {relative for relative, _ in files}:
        raise ValueError("Source file set changed after manifest verification")
    try:
        with atomic_output(destination, overwrite=overwrite) as temporary:
            with zipfile.ZipFile(temporary, mode="w", compression=zipfile.ZIP_STORED) as archive:
                for relative, path in files:
                    require_regular_path(path, base)
                    info = zipfile.ZipInfo(relative, date_time=FIXED_ZIP_TIMESTAMP)
                    info.create_system = 3
                    info.compress_type = zipfile.ZIP_STORED
                    info.external_attr = 0o100644 << 16
                    info.file_size = path.stat().st_size
                    digest = sha256()
                    size = 0
                    with path.open("rb") as source, archive.open(info, mode="w") as target:
                        for chunk in iter(lambda: source.read(COPY_CHUNK_SIZE), b""):
                            target.write(chunk)
                            digest.update(chunk)
                            size += len(chunk)
                    if expected is not None:
                        entry = expected[relative]
                        if size != entry.size or digest.hexdigest() != entry.sha256:
                            raise ValueError(f"Source changed while bundling: {relative}")
    except OSError as error:
        raise ValueError(f"Unable to write bundle: {destination}") from error
    return tuple(relative for relative, _ in files)


def create_bundle_from_manifest(
    root: str | Path, output: str | Path, manifest_path: str | Path,
    *, overwrite: bool = True,
) -> tuple[str, ...]:
    """Load a manifest and create a bundle with integrity verification."""
    return create_bundle(root, output, manifest=load_manifest(manifest_path), overwrite=overwrite)
