"""Read-only command-line interface for public release metadata."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from .catalog import release


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Nebula Public Edition metadata")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("info", "catalog", "version"),
        default="info",
        help="Metadata view to print (default: info)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "version":
        print(release.version)
        return 0

    payload = release.to_dict()
    if args.command == "info":
        payload = {
            "name": payload["name"],
            "version": payload["version"],
            "summary": payload["summary"],
        }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
