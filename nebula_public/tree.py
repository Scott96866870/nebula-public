"""Shared release-tree traversal that never descends into filesystem links."""

from __future__ import annotations

from pathlib import Path
import stat
from typing import Iterator


IGNORED_DIRECTORIES = frozenset({".git", ".pytest_cache", "__pycache__"})


def is_link(path: Path) -> bool:
    """Include Windows junctions and other reparse points in the link policy."""
    metadata = path.lstat()
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def public_paths(root: Path) -> Iterator[Path]:
    """Yield paths deterministically, pruning ignored directories and links."""
    for path in sorted(root.iterdir()):
        if is_link(path):
            yield path
        elif path.is_dir():
            if path.name not in IGNORED_DIRECTORIES:
                yield path
                yield from public_paths(path)
        else:
            yield path


def require_regular_path(path: Path, root: Path) -> None:
    if is_link(path):
        raise ValueError(f"Filesystem links are not supported: {path.relative_to(root).as_posix()}")
