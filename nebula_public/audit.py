"""Local checks that keep a public distribution within its declared boundary."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from fnmatch import fnmatch
from pathlib import Path


IGNORED_DIRECTORIES = frozenset({".git", ".pytest_cache", "__pycache__"})
BLOCKED_PATH_PATTERNS = (
    ".env",
    ".env.*",
    "*.local.json",
    "secrets.json",
    "config.json",
    "telemetry*.jsonl",
    "relay_intel.json",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa",
)
BLOCKED_DIRECTORY_NAMES = frozenset({"build", "dist", "venv", ".venv"})
REQUIRED_FILES = ("README.md", "pyproject.toml", "docs/PUBLIC_SCOPE.md")


@dataclass(frozen=True)
class AuditViolation:
    """One file or directory that must not be included in a public release."""

    path: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class AuditReport:
    """Result of a deterministic local public-boundary check."""

    root: str
    checked_files: int
    violations: tuple[AuditViolation, ...]

    @property
    def ok(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict[str, object]:
        return {
            "checked_files": self.checked_files,
            "ok": self.ok,
            "root": self.root,
            "violations": [item.to_dict() for item in self.violations],
        }


def audit_public_tree(root: str | Path) -> AuditReport:
    """Inspect a local tree for files excluded from the public release."""
    base = Path(root).resolve()
    if not base.is_dir():
        raise ValueError(f"Audit path is not a directory: {base}")

    violations: list[AuditViolation] = []
    checked_files = 0
    for path in sorted(base.rglob("*")):
        relative = path.relative_to(base)
        if any(part in IGNORED_DIRECTORIES for part in relative.parts):
            continue
        if path.is_dir():
            if path.name in BLOCKED_DIRECTORY_NAMES:
                violations.append(AuditViolation(relative.as_posix(), "blocked directory"))
            continue

        checked_files += 1
        if any(fnmatch(path.name, pattern) for pattern in BLOCKED_PATH_PATTERNS):
            violations.append(AuditViolation(relative.as_posix(), "blocked file pattern"))

    for required in REQUIRED_FILES:
        if not (base / required).is_file():
            violations.append(AuditViolation(required, "required public file is missing"))

    return AuditReport(
        root=str(base),
        checked_files=checked_files,
        violations=tuple(sorted(violations, key=lambda item: (item.path, item.reason))),
    )
