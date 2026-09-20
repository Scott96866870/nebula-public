"""Regressions for output paths, archive exclusions and filesystem links."""

import io
import os
from pathlib import Path
import subprocess
from contextlib import redirect_stdout
from tempfile import TemporaryDirectory
import unittest
import zipfile

from nebula_public.__main__ import main
from nebula_public.audit import audit_public_tree
from nebula_public.bundle import create_bundle
from nebula_public.manifest import build_manifest, load_manifest, verify_manifest
from nebula_public.report import build_release_report


class ReleaseBoundaryTests(unittest.TestCase):
    def make_tree(self, root):
        root.mkdir()
        (root / "docs").mkdir()
        for name in ("README.md", "pyproject.toml", "docs/PUBLIC_SCOPE.md"):
            (root / name).write_text("fixture", encoding="utf-8")

    def test_relative_cli_output_uses_working_directory(self):
        previous = Path.cwd()
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            self.make_tree(base / "source")
            try:
                os.chdir(base)
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main([
                        "manifest", "--path", "source", "--output", "source/manifest.json"
                    ]), 0)
                    self.assertEqual(main([
                        "verify", "--path", "source", "--manifest", "source/manifest.json"
                    ]), 0)
                manifest = load_manifest("source/manifest.json")
                self.assertEqual(manifest.excluded_paths, ("manifest.json",))
            finally:
                os.chdir(previous)

    def test_bundle_contains_only_manifest_files(self):
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "source"
            self.make_tree(root)
            notes = root / "private-notes.txt"
            notes.write_text("before", encoding="utf-8")
            manifest_path = root / "manifest.json"
            manifest = build_manifest(root, exclude=(notes, manifest_path))
            manifest_path.write_text(manifest.to_json(), encoding="utf-8")
            notes.write_text("after", encoding="utf-8")
            output = root / "release.zip"
            expected = tuple(entry.path for entry in manifest.entries)
            self.assertEqual(create_bundle(root, output, manifest=manifest), expected)
            first = output.read_bytes()
            self.assertEqual(create_bundle(root, output, manifest=manifest), expected)
            self.assertEqual(first, output.read_bytes())
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(tuple(archive.namelist()), expected)

    def test_ignored_directory_is_pruned_but_same_named_file_is_included(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            self.make_tree(root)
            (root / ".git").mkdir()
            (root / ".git" / "secrets.json").write_text("{}", encoding="utf-8")
            (root / "__pycache__").write_text("ordinary file", encoding="utf-8")
            self.assertTrue(audit_public_tree(root).ok)
            paths = [entry.path for entry in build_manifest(root).entries]
            self.assertIn("__pycache__", paths)
            self.assertNotIn(".git/secrets.json", paths)

    def assert_link_blocked(self, root, link, manifest):
        audit = audit_public_tree(root)
        self.assertFalse(audit.ok)
        self.assertIn((link.name, "filesystem link"), [
            (item.path, item.reason) for item in audit.violations
        ])
        self.assertFalse(build_release_report(root).ok)
        with self.assertRaisesRegex(ValueError, "Filesystem links"):
            build_manifest(root)
        with self.assertRaisesRegex(ValueError, "Filesystem links"):
            verify_manifest(root, manifest)
        output = root.parent / "release.zip"
        with self.assertRaisesRegex(ValueError, "Public boundary"):
            create_bundle(root, output)
        self.assertFalse(output.exists())

    def test_file_directory_and_broken_symlinks_are_rejected(self):
        for kind in ("file", "directory", "broken", "ignored"):
            with self.subTest(kind=kind), TemporaryDirectory() as temporary:
                base = Path(temporary)
                root = base / "source"
                self.make_tree(root)
                manifest = build_manifest(root)
                target = base / "outside"
                if kind in ("directory", "ignored"):
                    target.mkdir()
                    (target / "notes.txt").write_text("outside", encoding="utf-8")
                elif kind == "file":
                    target.write_text("outside", encoding="utf-8")
                link = root / (".git" if kind == "ignored" else "linked")
                try:
                    link.symlink_to(target, target_is_directory=kind in ("directory", "ignored"))
                except OSError as error:
                    self.skipTest(f"Symlink creation is unavailable: {error}")
                self.assert_link_blocked(root, link, manifest)

    @unittest.skipUnless(os.name == "nt", "Windows junction regression")
    def test_windows_junction_is_rejected_without_reading_target(self):
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "source"
            self.make_tree(root)
            manifest = build_manifest(root)
            target = base / "outside"
            target.mkdir()
            (target / "notes.txt").write_text("outside", encoding="utf-8")
            link = root / "junction"
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            try:
                self.assert_link_blocked(root, link, manifest)
            finally:
                link.rmdir()


if __name__ == "__main__":
    unittest.main()
