"""Failure injection tests for complete, bounded-memory release outputs."""

from contextlib import redirect_stdout
from hashlib import sha256
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

from nebula_public.__main__ import main
from nebula_public.bundle import COPY_CHUNK_SIZE, create_bundle
from nebula_public.manifest import build_manifest, verify_manifest
from nebula_public.output import atomic_output, write_text_output


class ReleaseOutputTests(unittest.TestCase):
    def make_tree(self, root):
        root.mkdir()
        (root / "docs").mkdir()
        for name in ("README.md", "pyproject.toml", "docs/PUBLIC_SCOPE.md"):
            (root / name).write_text("fixture", encoding="utf-8")

    def assert_no_temporary_files(self, directory):
        self.assertEqual(list(directory.glob(".nebula-*.tmp")), [])

    def test_failed_writer_preserves_original_or_absent_destination(self):
        for existing in (False, True):
            with self.subTest(existing=existing), TemporaryDirectory() as temporary:
                root = Path(temporary)
                output = root / "output.txt"
                if existing:
                    output.write_bytes(b"original")
                with self.assertRaisesRegex(OSError, "disk full"):
                    with atomic_output(output) as staged:
                        staged.write_bytes(b"incomplete")
                        raise OSError("disk full")
                self.assertEqual(output.read_bytes() if existing else output.exists(),
                                 b"original" if existing else False)
                self.assert_no_temporary_files(root)

    def test_no_overwrite_resists_destination_created_during_write(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output.txt"
            with self.assertRaises(FileExistsError):
                with atomic_output(output, overwrite=False) as staged:
                    staged.write_bytes(b"our output")
                    output.write_bytes(b"other writer")
            self.assertEqual(output.read_bytes(), b"other writer")
            self.assert_no_temporary_files(root)

    def test_failed_replace_preserves_original_and_cleans_staging(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output.txt"
            output.write_bytes(b"original")
            with patch("nebula_public.output.os.replace", side_effect=PermissionError("locked")):
                with self.assertRaises(PermissionError):
                    write_text_output(output, "replacement", overwrite=True)
            self.assertEqual(output.read_bytes(), b"original")
            self.assert_no_temporary_files(root)

    def test_text_outputs_use_utf8_lf_and_explicit_overwrite(self):
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "text.txt"
            write_text_output(output, "release ✓\n")
            self.assertEqual(output.read_bytes(), "release ✓\n".encode("utf-8"))
            with self.assertRaises(FileExistsError):
                write_text_output(output, "changed")
            write_text_output(output, "changed\n", overwrite=True)
            self.assertEqual(output.read_bytes(), b"changed\n")

    def test_streamed_archive_matches_manifest_and_is_reproducible(self):
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "source"
            self.make_tree(root)
            payload = b"A" * (COPY_CHUNK_SIZE * 2 + 71)
            (root / "large.bin").write_bytes(payload)
            manifest = build_manifest(root)
            output = root / "release.zip"
            with patch.object(Path, "read_bytes", side_effect=AssertionError("unbounded read")):
                create_bundle(root, output, manifest=manifest)
            first = output.read_bytes()
            create_bundle(root, output, manifest=manifest)
            self.assertEqual(first, output.read_bytes())
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(archive.namelist(), [entry.path for entry in manifest.entries])
                for entry in manifest.entries:
                    content = archive.read(entry.path)
                    self.assertEqual(sha256(content).hexdigest(), entry.sha256)
                    self.assertEqual(len(content), entry.size)
                self.assertTrue(all(info.create_system == 3 for info in archive.infolist()))
            self.assert_no_temporary_files(root)

    def test_changed_bytes_after_verification_do_not_replace_archive(self):
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "source"
            self.make_tree(root)
            output = base / "release.zip"
            manifest = build_manifest(root)
            create_bundle(root, output, manifest=manifest)
            original = output.read_bytes()

            def verify_then_change(*args, **kwargs):
                result = verify_manifest(*args, **kwargs)
                (root / "README.md").write_text("changed", encoding="utf-8")
                return result

            with patch("nebula_public.bundle.verify_manifest", side_effect=verify_then_change):
                with self.assertRaisesRegex(ValueError, "Source changed while bundling"):
                    create_bundle(root, output, manifest=manifest)
            self.assertEqual(output.read_bytes(), original)
            self.assert_no_temporary_files(base)

    def test_new_file_after_verification_is_not_published(self):
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "source"
            self.make_tree(root)
            manifest = build_manifest(root)

            def verify_then_add(*args, **kwargs):
                result = verify_manifest(*args, **kwargs)
                (root / "extra.txt").write_text("new", encoding="utf-8")
                return result

            output = base / "release.zip"
            with patch("nebula_public.bundle.verify_manifest", side_effect=verify_then_add):
                with self.assertRaisesRegex(ValueError, "file set changed"):
                    create_bundle(root, output, manifest=manifest)
            self.assertFalse(output.exists())

    def test_bundle_read_failure_preserves_archive(self):
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "source"
            self.make_tree(root)
            output = base / "release.zip"
            output.write_bytes(b"existing archive")
            original_open = Path.open

            def fail_on_readme(path, *args, **kwargs):
                if path == root / "README.md":
                    raise PermissionError("fixture unreadable")
                return original_open(path, *args, **kwargs)

            with patch.object(Path, "open", fail_on_readme):
                with self.assertRaises(ValueError):
                    create_bundle(root, output)
            self.assertEqual(output.read_bytes(), b"existing archive")
            self.assert_no_temporary_files(base)

    def test_cli_io_errors_return_json_and_status_two(self):
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "source"
            self.make_tree(root)
            output = base / "release.out"
            for command in ("manifest", "export", "bundle"):
                with self.subTest(command=command):
                    args = [command, "--output", str(output)]
                    if command != "export":
                        args += ["--path", str(root)]
                    stream = io.StringIO()
                    with patch("nebula_public.output.os.link", side_effect=OSError("disk full")):
                        with redirect_stdout(stream):
                            status = main(args)
                    self.assertEqual(status, 2)
                    self.assertFalse(json.loads(stream.getvalue())["ok"])
                    self.assertFalse(output.exists())
                    self.assert_no_temporary_files(base)

    def test_cli_scan_errors_return_json_and_status_two(self):
        with patch("nebula_public.__main__.audit_public_tree", side_effect=PermissionError("denied")):
            stream = io.StringIO()
            with redirect_stdout(stream):
                status = main(["verify"])
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(stream.getvalue()), {"ok": False, "error": "denied"})

    def test_cli_force_replaces_complete_output(self):
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "source"
            self.make_tree(root)
            output = base / "release.zip"
            output.write_bytes(b"original")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["bundle", "--path", str(root), "--output", str(output)]), 2)
                self.assertEqual(output.read_bytes(), b"original")
                self.assertEqual(main([
                    "bundle", "--path", str(root), "--output", str(output), "--force"
                ]), 0)
            with zipfile.ZipFile(output) as archive:
                self.assertIn("README.md", archive.namelist())


if __name__ == "__main__":
    unittest.main()
