"""Public-boundary names have identical matching rules on all platforms."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nebula_public.__main__ import main
from nebula_public.audit import audit_public_tree
from nebula_public.bundle import create_bundle
from nebula_public.manifest import build_manifest
from nebula_public.report import build_release_report


class AuditCaseTests(unittest.TestCase):
    def make_tree(self, root):
        (root / "docs").mkdir()
        for name in ("README.md", "pyproject.toml", "docs/PUBLIC_SCOPE.md"):
            (root / name).write_text("fixture", encoding="utf-8")

    def test_blocked_files_match_uppercase_and_mixed_case(self):
        names = (
            ".ENV", ".EnV.Production", "Settings.LOCAL.JSON", "SECRETS.JSON",
            "Config.Json", "TELEMETRY-2026.JSONL", "Relay_Intel.Json",
            "Certificate.PEM", "Private.KEY", "Identity.P12", "Identity.PFX", "ID_RSA",
        )
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_tree(root)
            nested = root / "docs" / "Nested"
            nested.mkdir()
            for name in names:
                (nested / name).write_text("fixture", encoding="utf-8")
            report = audit_public_tree(root)
            self.assertFalse(report.ok)
            self.assertEqual(
                [(item.path, item.reason) for item in report.violations],
                sorted((f"docs/Nested/{name}", "blocked file pattern") for name in names),
            )

    def test_blocked_directories_match_case_and_report_original_paths(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_tree(root)
            for name in ("BUILD", "Dist", "VENV", ".Venv"):
                (root / "docs" / name).mkdir()
            report = audit_public_tree(root)
            self.assertEqual(
                [(item.path, item.reason) for item in report.violations],
                [(f"docs/{name}", "blocked directory") for name in (".Venv", "BUILD", "Dist", "VENV")],
            )

    def test_similar_public_names_are_not_blocked(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_tree(root)
            for name in ("CONFIG.JSON.md", "PRIVATE.KEY.txt", "ID_RSA.pub", "ENV", "telemetry.csv", "build"):
                (root / name).write_text("public", encoding="utf-8")
            for name in ("BUILDING", "Distribution", "VENV-notes"):
                (root / name).mkdir()
            self.assertTrue(audit_public_tree(root).ok)

    def test_verify_and_report_reject_case_variants(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_tree(root)
            (root / "CONFIG.JSON").write_text("{}", encoding="utf-8")
            self.assertFalse(build_release_report(root).ok)
            for command in ("verify", "report"):
                with self.subTest(command=command):
                    stream = io.StringIO()
                    with redirect_stdout(stream):
                        status = main([command, "--path", str(root)])
                    self.assertEqual(status, 1)
                    payload = json.loads(stream.getvalue())
                    self.assertFalse(payload["ok"])
                    boundary = payload if command == "verify" else payload["boundary"]
                    self.assertEqual(boundary["violations"][0]["path"], "CONFIG.JSON")

    def test_bundle_preserves_destination_even_with_manifest_exclusion(self):
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "source"
            root.mkdir()
            self.make_tree(root)
            blocked = root / "Private.KEY"
            blocked.write_text("fixture", encoding="utf-8")
            manifest = build_manifest(root, exclude=(blocked,))
            destination = base / "release.zip"
            destination.write_bytes(b"existing archive")
            for supplied_manifest in (None, manifest):
                with self.subTest(manifest=supplied_manifest is not None):
                    with self.assertRaisesRegex(ValueError, "Public boundary check failed: Private.KEY"):
                        create_bundle(root, destination, manifest=supplied_manifest)
                    self.assertEqual(destination.read_bytes(), b"existing archive")
                    self.assertEqual(list(base.glob(".nebula-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
