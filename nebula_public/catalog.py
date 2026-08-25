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


release = PublicRelease(
    name="Nebula Public Edition",
    version="0.1.0",
    summary="A read-only public overview and metadata release.",
    included=(
        "Public documentation",
        "Release metadata",
        "Local read-only command-line interface",
    ),
    excluded=(
        "Operational modules",
        "Local configuration and telemetry",
        "Private project materials and build artifacts",
    ),
)
