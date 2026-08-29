"""Tests for the public release metadata command."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from nebula_public.audit import audit_public_tree
from nebula_public.bundle import create_bundle
from nebula_public.__main__ import main
from nebula_public.manifest import (
    build_manifest,
    compare_manifests,
    load_manifest,
    verify_manifest,
)


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
        self.assertEqual(payload["version"], "0.5.0")
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

    def test_manifest_diff_reports_release_file_changes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_public_tree(root)
            (root / "old.py").write_text("old", encoding="utf-8")
            earlier = build_manifest(root)

            (root / "old.py").write_text("changed", encoding="utf-8")
            (root / "new.py").write_text("new", encoding="utf-8")
            later = build_manifest(root)

            diff = compare_manifests(earlier, later)

        self.assertTrue(diff.changed)
        self.assertEqual(diff.added, ("new.py",))
        self.assertEqual(diff.modified, ("old.py",))
        self.assertIn("## Added", diff.to_markdown())

    def test_cli_diff_supports_json_and_markdown(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_public_tree(root)
            left_path = root / "left.json"
            right_path = root / "right.json"
            left_path.write_text(
                build_manifest(root, exclude=(left_path, right_path)).to_json(),
                encoding="utf-8",
            )
            (root / "new.py").write_text("new", encoding="utf-8")
            right_path.write_text(
                build_manifest(root, exclude=(left_path, right_path)).to_json(),
                encoding="utf-8",
            )

            status, output = self.run_command(
                "diff", str(left_path), str(right_path), "--format", "json"
            )
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["added"], ["new.py"])

            status, output = self.run_command(
                "diff", str(left_path), str(right_path), "--format", "markdown"
            )

        self.assertEqual(status, 0)
        self.assertIn("# Manifest diff", output)

    def test_bundle_is_reproducible_and_excludes_its_destination(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_public_tree(root)
            (root / "module.py").write_text("value = 1\n", encoding="utf-8")
            output = root / "public.zip"

            first_files = create_bundle(root, output)
            first_bytes = output.read_bytes()
            second_files = create_bundle(root, output)
            second_bytes = output.read_bytes()

            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()

        self.assertEqual(first_files, second_files)
        self.assertEqual(first_bytes, second_bytes)
        self.assertEqual(names, sorted(names))
        self.assertNotIn("public.zip", names)

    def test_bundle_refuses_a_blocked_tree(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_public_tree(root)
            (root / "config.json").write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Public boundary check failed"):
                create_bundle(root, root / "public.zip")

    def test_cli_bundle_reports_archive_contents(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_public_tree(root)
            output = root / "public.zip"
            status, printed = self.run_command(
                "bundle", "--path", str(root), "--output", str(output)
            )

            self.assertEqual(status, 0)
            payload = json.loads(printed)
            self.assertTrue(payload["ok"])
            self.assertIn("README.md", payload["files"])
            self.assertTrue(output.is_file())

    def test_bundle_can_rebuild_existing_destination_with_manifest(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_public_tree(root)
            manifest_path = root / "release-manifest.json"
            manifest_path.write_text(
                build_manifest(root, exclude=(manifest_path,)).to_json(),
                encoding="utf-8",
            )
            output = root / "public.zip"

            first_status, _ = self.run_command(
                "bundle",
                "--path",
                str(root),
                "--output",
                str(output),
                "--manifest",
                str(manifest_path),
            )
            second_status, second_output = self.run_command(
                "bundle",
                "--path",
                str(root),
                "--output",
                str(output),
                "--manifest",
                str(manifest_path),
                "--force",
            )

        self.assertEqual(first_status, 0)
        self.assertEqual(second_status, 0)
        self.assertTrue(json.loads(second_output)["ok"])


if __name__ == "__main__":
    unittest.main()
