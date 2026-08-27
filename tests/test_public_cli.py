"""Tests for the public release metadata command."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nebula_public.audit import audit_public_tree
from nebula_public.__main__ import main
from nebula_public.manifest import build_manifest, load_manifest, verify_manifest


class PublicCliTests(unittest.TestCase):
    def make_public_tree(self, root: Path) -> None:
        (root / "README.md").write_text("test", encoding="utf-8")
        (root / "pyproject.toml").write_text("test", encoding="utf-8")
        (root / "docs").mkdir()
        (root / "docs" / "PUBLIC_SCOPE.md").write_text("test", encoding="utf-8")

    def run_command(self, *args: str) -> tuple[int, str]:
        stream = io.StringIO()
        with redirect_stdout(stream):
            status = main(args)
        return status, stream.getvalue()

    def run_json_command(self, *args: str) -> dict[str, object]:
        status, output = self.run_command(*args)
        self.assertEqual(status, 0)
        return json.loads(output)

    def test_default_info_is_read_only_metadata(self) -> None:
        payload = self.run_json_command()
        self.assertEqual(payload["name"], "Nebula Public Edition")
        self.assertEqual(payload["version"], "0.3.0")
        self.assertNotIn("excluded", payload)

    def test_catalog_describes_public_boundary(self) -> None:
        payload = self.run_json_command("catalog")
        self.assertIn("Public documentation", payload["included"])
        self.assertIn("Operational modules", payload["excluded"])

    def test_catalog_can_render_markdown(self) -> None:
        status, output = self.run_command("catalog", "--format", "markdown")
        self.assertEqual(status, 0)
        self.assertIn("# Nebula Public Edition", output)
        self.assertIn("## Excluded", output)

    def test_verifier_passes_for_public_project(self) -> None:
        payload = self.run_json_command("verify", "--path", ".")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["violations"], [])

    def test_verifier_reports_blocked_local_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_public_tree(root)
            (root / "config.local.json").write_text("{}", encoding="utf-8")

            report = audit_public_tree(root)

        self.assertFalse(report.ok)
        self.assertEqual(report.violations[0].path, "config.local.json")

    def test_export_creates_requested_markdown_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "release-card.md"
            status, printed_path = self.run_command(
                "export", "--output", str(output)
            )

            self.assertEqual(status, 0)
            self.assertEqual(Path(printed_path.strip()), output.resolve())
            self.assertIn("# Nebula Public Edition", output.read_text(encoding="utf-8"))

    def test_export_does_not_overwrite_without_force(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "release-card.md"
            output.write_text("original", encoding="utf-8")

            status, message = self.run_command("export", "--output", str(output))

            self.assertEqual(status, 2)
            self.assertIn("Refusing to overwrite", message)
            self.assertEqual(output.read_text(encoding="utf-8"), "original")

    def test_manifest_round_trip_and_integrity_check(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_public_tree(root)
            tracked_file = root / "package.py"
            tracked_file.write_text("version = 1\n", encoding="utf-8")
            removed_file = root / "removed.py"
            removed_file.write_text("remove me\n", encoding="utf-8")

            manifest = build_manifest(root)
            self.assertTrue(verify_manifest(root, manifest).ok)

            tracked_file.write_text("version = 2\n", encoding="utf-8")
            removed_file.unlink()
            (root / "unexpected.txt").write_text("new", encoding="utf-8")
            report = verify_manifest(root, manifest)

        self.assertFalse(report.ok)
        self.assertEqual(report.modified, ("package.py",))
        self.assertEqual(report.missing, ("removed.py",))
        self.assertEqual(report.unexpected, ("unexpected.txt",))

    def test_cli_manifest_excludes_its_output_and_verifies_cleanly(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_public_tree(root)
            manifest_path = root / "release-manifest.json"
            status, printed_path = self.run_command(
                "manifest", "--path", str(root), "--output", str(manifest_path)
            )

            self.assertEqual(status, 0)
            self.assertEqual(Path(printed_path.strip()), manifest_path.resolve())
            self.assertEqual(load_manifest(manifest_path).excluded_paths, ("release-manifest.json",))

            status, output = self.run_command(
                "verify", "--path", str(root), "--manifest", str(manifest_path)
            )

        self.assertEqual(status, 0)
        payload = json.loads(output)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["integrity"]["ok"])


if __name__ == "__main__":
    unittest.main()
