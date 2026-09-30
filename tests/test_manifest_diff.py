"""Semantic manifest comparisons and optional CI exit statuses."""

from contextlib import redirect_stdout
from dataclasses import replace
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nebula_public.__main__ import main
from nebula_public.manifest import ManifestEntry, ReleaseManifest, compare_manifests


class ManifestDiffTests(unittest.TestCase):
    def setUp(self):
        self.left = ReleaseManifest(
            1, "Fixture", "1.0", (ManifestEntry("a.txt", 1, "a" * 64),),
            ("notes.txt",),
        )

    def run_diff(self, right, *args):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            left_path, right_path = root / "left.json", root / "right.json"
            left_path.write_text(self.left.to_json(), encoding="utf-8")
            right_path.write_text(right.to_json(), encoding="utf-8")
            stream = io.StringIO()
            with redirect_stdout(stream):
                status = main(["diff", str(left_path), str(right_path), *args])
            return status, stream.getvalue()

    def test_metadata_only_changes_are_reported(self):
        for changes in ({"release_name": "New name"}, {"release_version": "2.0"}):
            with self.subTest(changes=changes):
                diff = compare_manifests(self.left, replace(self.left, **changes))
                self.assertTrue(diff.changed)
                self.assertTrue(diff.to_dict()["metadata_changed"])
                self.assertEqual(diff.unchanged, ("a.txt",))
                self.assertFalse(diff.added or diff.removed or diff.modified)
                self.assertIn("**Release metadata changed:** yes", diff.to_markdown())

    def test_metadata_comparison_does_not_conflate_display_labels(self):
        left = replace(self.left, release_name="Fixture A", release_version="B")
        right = replace(self.left, release_name="Fixture", release_version="A B")
        diff = compare_manifests(left, right)
        self.assertEqual(diff.left_release, diff.right_release)
        self.assertTrue(diff.metadata_changed)

    def test_exclusion_only_changes_are_reported_in_both_formats(self):
        diff = compare_manifests(
            self.left, replace(self.left, excluded_paths=("z.txt", "b.txt"))
        )
        self.assertTrue(diff.changed)
        self.assertFalse(diff.metadata_changed)
        self.assertEqual(diff.to_dict()["exclusions_added"], ["b.txt", "z.txt"])
        self.assertEqual(diff.to_dict()["exclusions_removed"], ["notes.txt"])
        self.assertIn("## Exclusions added\n\n- b.txt\n- z.txt", diff.to_markdown())
        self.assertIn("## Exclusions removed\n\n- notes.txt", diff.to_markdown())

    def test_order_changes_are_not_semantic_changes(self):
        left = replace(self.left, entries=(
            *self.left.entries, ManifestEntry("b.txt", 2, "b" * 64),
        ), excluded_paths=("notes.txt", "other.txt"))
        right = replace(left, entries=left.entries[::-1], excluded_paths=left.excluded_paths[::-1])
        diff = compare_manifests(left, right)
        self.assertFalse(diff.changed)
        self.assertFalse(diff.metadata_changed)
        self.assertEqual(diff.unchanged, ("a.txt", "b.txt"))
        self.assertEqual(diff.exclusions_added, ())
        self.assertEqual(diff.exclusions_removed, ())

    def test_check_reports_all_change_types_without_suppressing_output(self):
        changes = (
            {"release_version": "2.0"},
            {"excluded_paths": ("extra.txt", "notes.txt")},
            {"excluded_paths": ()},
            {"entries": (*self.left.entries, ManifestEntry("b.txt", 0, "b" * 64))},
            {"entries": ()},
            {"entries": (ManifestEntry("a.txt", 2, "b" * 64),)},
        )
        for values in changes:
            for output_format in ("json", "markdown"):
                with self.subTest(changes=values, format=output_format):
                    status, output = self.run_diff(
                        replace(self.left, **values), "--check", "--format", output_format
                    )
                    self.assertEqual(status, 1)
                    if output_format == "json":
                        self.assertTrue(json.loads(output)["changed"])
                    else:
                        self.assertIn("**Changed:** yes", output)

    def test_check_returns_zero_when_manifests_match(self):
        status, output = self.run_diff(self.left, "--check")
        self.assertEqual(status, 0)
        self.assertFalse(json.loads(output)["changed"])

    def test_default_exit_status_remains_zero_when_metadata_differs(self):
        status, output = self.run_diff(replace(self.left, release_version="2.0"))
        self.assertEqual(status, 0)
        self.assertTrue(json.loads(output)["changed"])

    def test_check_returns_two_for_invalid_input(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.json"
            path.write_text("{", encoding="utf-8")
            stream = io.StringIO()
            with redirect_stdout(stream):
                status = main(["diff", str(path), str(path), "--check"])
            self.assertEqual(status, 2)
            self.assertFalse(json.loads(stream.getvalue())["ok"])


if __name__ == "__main__":
    unittest.main()
