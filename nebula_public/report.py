"""Aggregated release-readiness reports for the public distribution."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from html import escape
from pathlib import Path
import re

from .audit import AuditReport, audit_public_tree
from .tree import is_link, public_paths
from .catalog import release
from .manifest import IntegrityReport, ReleaseManifest, verify_manifest


def _markdown_text(value: str) -> str:
    """Keep filenames literal and on one line in Markdown lists."""
    value = "".join(
        f"\\x{ord(char):02x}" if ord(char) < 32 or ord(char) == 127 else char
        for char in value
    )
    return re.sub(r"([\\`*_\[\]{}()#+.!|~>-])", r"\\\1", escape(value, quote=False))


@dataclass(frozen=True)
class ExtensionSummary:
    """File count and byte total for one extension group."""

    extension: str
    files: int
    bytes: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ReleaseReport:
    """One release-readiness snapshot assembled from local checks."""

    root: str
    release_name: str
    release_version: str
    boundary: AuditReport
    integrity: IntegrityReport | None
    manifest_release_match: bool | None
    file_count: int
    total_bytes: int
    extensions: tuple[ExtensionSummary, ...]
    recommendations: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return (
            self.boundary.ok
            and (self.integrity is None or self.integrity.ok)
            and self.manifest_release_match is not False
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "boundary": self.boundary.to_dict(),
            "extensions": [item.to_dict() for item in self.extensions],
            "file_count": self.file_count,
            "integrity": self.integrity.to_dict() if self.integrity else None,
            "manifest_release_match": self.manifest_release_match,
            "ok": self.ok,
            "recommendations": list(self.recommendations),
            "release": {"name": self.release_name, "version": self.release_version},
            "root": self.root,
            "total_bytes": self.total_bytes,
        }

    def to_markdown(self) -> str:
        """Render a compact review report for a release description."""
        status = "READY" if self.ok else "ACTION REQUIRED"
        lines = [
            f"# Release report: {self.release_name} {self.release_version}",
            "",
            f"**Status:** {status}",
            f"**Files:** {self.file_count}",
            f"**Bytes:** {self.total_bytes}",
            "",
            "## Checks",
            "",
            f"- Public boundary: {'pass' if self.boundary.ok else 'fail'}",
            f"- Manifest integrity: {self._check_label(self.integrity)}",
            f"- Manifest version: {self._match_label()}",
        ]
        if self.boundary.violations:
            lines.extend(["", "## Boundary violations", ""])
            lines.extend(
                f"- {_markdown_text(item.path)}: {_markdown_text(item.reason)}"
                for item in self.boundary.violations
            )
        if self.integrity is not None:
            lines.extend([
                "", "## Manifest integrity details", "",
                f"**Expected files:** {self.integrity.expected_files}",
                f"**Actual files:** {self.integrity.actual_files}",
            ])
            for heading, paths in (
                ("Missing", self.integrity.missing),
                ("Modified", self.integrity.modified),
                ("Unexpected", self.integrity.unexpected),
            ):
                lines.extend(["", f"### {heading}", ""])
                lines.extend(f"- {_markdown_text(path)}" for path in paths)
                if not paths:
                    lines.append("- None")
        lines.extend(["", "## File Types", ""])
        if self.extensions:
            lines.extend(
                f"- {_markdown_text(item.extension)}: {item.files} file(s), {item.bytes} bytes"
                for item in self.extensions
            )
        else:
            lines.append("- None")
        lines.extend(["", "## Recommendations", ""])
        lines.extend(f"- {item}" for item in self.recommendations)
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _check_label(report: IntegrityReport | None) -> str:
        if report is None:
            return "not requested"
        return "pass" if report.ok else "fail"

    def _match_label(self) -> str:
        if self.manifest_release_match is None:
            return "not requested"
        return "pass" if self.manifest_release_match else "fail"


def _file_statistics(root: Path) -> tuple[int, int, tuple[ExtensionSummary, ...]]:
    totals: dict[str, list[int]] = {}
    for path in public_paths(root):
        if is_link(path) or not path.is_file():
            continue
        extension = path.suffix.lower() or "(no extension)"
        bucket = totals.setdefault(extension, [0, 0])
        bucket[0] += 1
        bucket[1] += path.stat().st_size
    summaries = tuple(
        ExtensionSummary(extension, values[0], values[1])
        for extension, values in sorted(totals.items())
    )
    return sum(item.files for item in summaries), sum(item.bytes for item in summaries), summaries


def build_release_report(
    root: str | Path, *, manifest: ReleaseManifest | None = None
) -> ReleaseReport:
    """Build a local release-readiness report without network access."""
    base = Path(root).resolve()
    if not base.is_dir():
        raise ValueError(f"Report path is not a directory: {base}")

    boundary = audit_public_tree(base)
    integrity = verify_manifest(base, manifest) if manifest is not None else None
    manifest_release_match = (
        None
        if manifest is None
        else manifest.release_name == release.name and manifest.release_version == release.version
    )
    file_count, total_bytes, extensions = _file_statistics(base)

    recommendations: list[str] = []
    if not boundary.ok:
        recommendations.append("Remove excluded paths before publishing.")
    if integrity is not None and not integrity.ok:
        recommendations.append("Regenerate or fix the release manifest before publishing.")
    if manifest_release_match is False:
        recommendations.append("Use a manifest generated for the current release version.")
    if not recommendations:
        recommendations.append("Ready for public review.")

    return ReleaseReport(
        root=str(base),
        release_name=release.name,
        release_version=release.version,
        boundary=boundary,
        integrity=integrity,
        manifest_release_match=manifest_release_match,
        file_count=file_count,
        total_bytes=total_bytes,
        extensions=extensions,
        recommendations=tuple(recommendations),
    )
