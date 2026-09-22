"""Publish complete local outputs without exposing partial files."""

from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
from typing import Iterator

from .tree import is_link


def output_path(output: str | Path) -> Path:
    path = Path(output).expanduser().absolute()
    if not path.parent.is_dir():
        raise ValueError(f"Output directory does not exist: {path.parent}")
    if os.path.lexists(path):
        if is_link(path):
            raise ValueError(f"Output must not be a filesystem link: {path}")
        if not path.is_file():
            raise ValueError(f"Output is not a regular file: {path}")
    return path


@contextmanager
def atomic_output(output: str | Path, *, overwrite: bool = True) -> Iterator[Path]:
    """Stage beside the destination, then publish only after successful writing.

    Hard-link publication makes no-overwrite mode exclusive even if another
    process creates the destination while the output is being prepared.
    """
    destination = output_path(output)
    if not overwrite and os.path.lexists(destination):
        raise FileExistsError(f"Refusing to overwrite existing file: {destination}")
    descriptor, name = tempfile.mkstemp(prefix=".nebula-", suffix=".tmp", dir=destination.parent)
    temporary = Path(name)
    os.close(descriptor)
    try:
        yield temporary
        with temporary.open("r+b") as stream:
            os.fsync(stream.fileno())
        output_path(destination)
        if overwrite:
            os.replace(temporary, destination)
        else:
            os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def write_text_output(output: str | Path, text: str, *, overwrite: bool = False) -> None:
    with atomic_output(output, overwrite=overwrite) as temporary:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
