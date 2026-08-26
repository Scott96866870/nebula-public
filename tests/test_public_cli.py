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


class PublicCliTests(unittest.TestCase):
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
        self.assertEqual(payload["version"], "0.2.0")
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
            (root / "README.md").write_text("test", encoding="utf-8")
            (root / "pyproject.toml").write_text("test", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "PUBLIC_SCOPE.md").write_text("test", encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
