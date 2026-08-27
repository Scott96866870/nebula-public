"""Read-only command-line interface for public release metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .audit import audit_public_tree
from .catalog import release
from .manifest import build_manifest, load_manifest, verify_manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Nebula Public Edition metadata")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("info", help="Print a compact JSON release summary.")

    catalog_parser = subparsers.add_parser(
        "catalog", help="Print the complete release catalog."
    )
    catalog_parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Output format (default: json).",
    )

    verify_parser = subparsers.add_parser(
        "verify", help="Check a local tree against public-release exclusions."
    )
    verify_parser.add_argument(
        "--path",
        type=Path,
        default=Path.cwd(),
        help="Directory to inspect (default: current directory).",
    )
    verify_parser.add_argument(
        "--manifest",
        type=Path,
        help="Optional JSON manifest to compare against the local directory.",
    )

    manifest_parser = subparsers.add_parser(
        "manifest", help="Build a deterministic SHA-256 manifest for a local tree."
    )
    manifest_parser.add_argument(
        "--path",
        type=Path,
        default=Path.cwd(),
        help="Directory to record (default: current directory).",
    )
    manifest_parser.add_argument(
        "--output",
        type=Path,
        help="Optional local JSON destination. Prints to standard output when omitted.",
    )
    manifest_parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing manifest destination.",
    )

    export_parser = subparsers.add_parser(
        "export", help="Write the release catalog to a local file."
    )
    export_parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format (default: markdown).",
    )
    export_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination file path.",
    )
    export_parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing destination file.",
    )
    subparsers.add_parser("version", help="Print the release version.")
    return parser


def _release_output(format_name: str) -> str:
    if format_name == "markdown":
        return release.to_markdown()
    return json.dumps(release.to_dict(), indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    command = args.command or "info"
    if command == "version":
        print(release.version)
        return 0

    if command == "catalog":
        print(_release_output(args.format), end="")
        return 0

    if command == "verify":
        try:
            boundary_report = audit_public_tree(args.path)
            if args.manifest is not None:
                integrity_report = verify_manifest(
                    args.path, load_manifest(args.manifest)
                )
                payload = {
                    "boundary": boundary_report.to_dict(),
                    "integrity": integrity_report.to_dict(),
                    "ok": boundary_report.ok and integrity_report.ok,
                }
                print(json.dumps(payload, indent=2, sort_keys=True))
                return 0 if payload["ok"] else 1
        except ValueError as error:
            print(json.dumps({"ok": False, "error": str(error)}, indent=2))
            return 2
        print(json.dumps(boundary_report.to_dict(), indent=2, sort_keys=True))
        return 0 if boundary_report.ok else 1

    if command == "manifest":
        output = args.output.expanduser() if args.output is not None else None
        if output is not None and output.exists() and not args.force:
            print(f"Refusing to overwrite existing file: {output}")
            return 2
        if output is not None and not output.parent.is_dir():
            print(f"Output directory does not exist: {output.parent}")
            return 2
        try:
            manifest = build_manifest(args.path, exclude=(() if output is None else (output,)))
        except ValueError as error:
            print(json.dumps({"ok": False, "error": str(error)}, indent=2))
            return 2
        if output is None:
            print(manifest.to_json(), end="")
            return 0
        output.write_text(manifest.to_json(), encoding="utf-8")
        print(output.resolve())
        return 0

    if command == "export":
        output = args.output.expanduser()
        if output.exists() and not args.force:
            print(f"Refusing to overwrite existing file: {output}")
            return 2
        if not output.parent.is_dir():
            print(f"Output directory does not exist: {output.parent}")
            return 2
        output.write_text(_release_output(args.format), encoding="utf-8")
        print(output.resolve())
        return 0

    if command == "info":
        payload = release.to_dict()
        payload = {
            "name": payload["name"],
            "version": payload["version"],
            "summary": payload["summary"],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    raise AssertionError(f"Unhandled command: {command}")


if __name__ == "__main__":
    raise SystemExit(main())
