"""Literal text rendering shared by local Markdown reports."""

from html import escape
import re


def markdown_text(value: str) -> str:
    """Keep metadata and filenames literal and on one Markdown line."""
    value = "".join(
        f"\\x{ord(char):02x}" if ord(char) < 32 or ord(char) == 127 else char
        for char in value
    )
    return re.sub(r"([\\`*_\[\]{}()#+.!|~>-])", r"\\\1", escape(value, quote=False))
