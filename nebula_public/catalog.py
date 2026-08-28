"""Static, reviewable metadata for the public distribution."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PublicRelease:
    """Describes the intentionally limited public distribution."""

    name: str
    version: str
    summary: str
    included: tuple[str, ...]
    excluded: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return JSON-compatible release metadata."""
        return asdict(self)

    def to_markdown(self) -> str:
        """Render a portable, human-readable release card."""
        lines = [
            f"# {self.name}",
            "",
            f"**Version:** {self.version}",
            "",
            self.summary,
            "",
            "## Included",
            "",
            *(f"- {item}" for item in self.included),
            "",
            "## Excluded",
            "",
            *(f"- {item}" for item in self.excluded),
            "",
        ]
        return "\n".join(lines)


release = PublicRelease(
    name="Nebula Public Edition",
    version="0.4.0",
    summary="A local toolkit for cataloging, validating, verifying, and comparing public releases.",
    included=(
        "Public documentation",
        "Release metadata",
        "Local catalog, verification, export, integrity, and diff commands",
    ),
    excluded=(
        "Operational modules",
        "Local configuration and telemetry",
        "Private project materials and build artifacts",
    ),
)
