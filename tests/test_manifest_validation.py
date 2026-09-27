"""Reject ambiguous manifests before integrity checks or packaging."""

from contextlib import redirect_stdout
from dataclasses import replace
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nebula_public.__main__ import main
from nebula_public.manifest import (
    ManifestEntry, ReleaseManifest, build_manifest, load_manifest, verify_manifest,
)


class ManifestValidationTests(unittest.TestCase):
    def valid(self):
        return ReleaseManifest(1, "Fixture", "1.0", (ManifestEntry("a.txt", 0, "0" * 64),))

    def load_payload(self, payload):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return load_manifest(path)

    def test_schema_requires_integer_one(self):
        for value in (True, False, 1.0, "1", None, 2):
            with self.subTest(value=value):
                data = self.valid().to_dict()
                data["schema_version"] = value
                with self.assertRaises(ValueError):
                    self.load_payload(data)
                with self.assertRaises(ValueError):
                    replace(self.valid(), schema_version=value)

    def test_sizes_require_nonnegative_integers(self):
        for value in (True, False, 0.0, -1, "0", None):
            with self.subTest(value=value):
                data = self.valid().to_dict()
                data["files"][0]["size"] = value
                with self.assertRaises(ValueError):
                    self.load_payload(data)
                with self.assertRaises(ValueError):
                    replace(self.valid(), entries=(ManifestEntry("a.txt", value, "0" * 64),))

    def test_paths_use_identical_rules_on_all_platforms(self):
        for value in ("", ".", "..", "../a", "/a", "a/../b", "a//b", "./a",
                      "a/", "a/./b", "C:/a", "C:a", "a\\b", "//server/share/a",
                      "a:stream", "a\x00b", "a\nb", "a\x7fb"):
            for field in ("files", "excluded_paths"):
                with self.subTest(path=repr(value), field=field):
                    data = self.valid().to_dict()
                    if field == "files":
                        data[field][0]["path"] = value
                    else:
                        data[field] = [value]
                    with self.assertRaisesRegex(ValueError, "relative POSIX path"):
                        self.load_payload(data)

    def test_unicode_and_space_paths_round_trip(self):
        manifest = replace(self.valid(), entries=(ManifestEntry("资料/release notes.txt", 0, "a" * 64),))
        self.assertEqual(self.load_payload(manifest.to_dict()), manifest)

    def test_duplicate_json_fields_are_rejected_at_every_level(self):
        valid = json.dumps(self.valid().to_dict())
        examples = (
            valid.replace('"schema_version": 1', '"schema_version": 0, "schema_version": 1'),
            valid.replace('"size": 0', '"size": 5, "size": 0'),
            valid.replace('"name": "Fixture"', '"name": "Other", "name": "Fixture"'),
        )
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            for text in examples:
                with self.subTest(text=text):
                    path.write_text(text, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "duplicate JSON field"):
                        load_manifest(path)

    def test_duplicate_overlap_and_file_directory_conflicts(self):
        entry = self.valid().entries[0]
        cases = (
            {"entries": (entry, entry)},
            {"excluded_paths": ("other", "other")},
            {"excluded_paths": ("a.txt",)},
            {"entries": (entry, ManifestEntry("a.txt/child", 0, "0" * 64))},
        )
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.valid(), **changes)

    def test_invalid_release_metadata_is_rejected(self):
        for field in ("name", "version"):
            for value in ("", "  ", None, 1):
                with self.subTest(field=field, value=value):
                    data = self.valid().to_dict()
                    data["release"][field] = value
                    with self.assertRaises(ValueError):
                        self.load_payload(data)

    def test_python_api_rejects_mutable_or_malformed_entries(self):
        for changes in ({"entries": []}, {"excluded_paths": []}, {"entries": ({},)},
                        {"entries": (ManifestEntry("a", 0, "G" * 64),)},
                        {"entries": (ManifestEntry("a", 0, "short"),)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.valid(), **changes)

    def test_repeated_exclusions_generate_loadable_manifest(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "manifest.json"
            (root / "a.txt").write_text("fixture", encoding="utf-8")
            manifest = build_manifest(root, exclude=(output, output, "manifest.json"))
            self.assertEqual(manifest.excluded_paths, ("manifest.json",))
            output.write_text(manifest.to_json(), encoding="utf-8")
            self.assertTrue(verify_manifest(root, load_manifest(output)).ok)

    def test_invalid_utf8_and_json_return_cli_error_without_output(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            bad = root / "bad.json"
            good = root / "good.json"
            good.write_text(self.valid().to_json(), encoding="utf-8")
            for content in (b"\xff", b"{", b'{"schema_version":true}'):
                with self.subTest(content=content):
                    bad.write_bytes(content)
                    with self.assertRaises(ValueError):
                        load_manifest(bad)
                    stream = io.StringIO()
                    with redirect_stdout(stream):
                        status = main(["diff", str(good), str(bad)])
                    self.assertEqual(status, 2)
                    self.assertFalse(json.loads(stream.getvalue())["ok"])


if __name__ == "__main__":
    unittest.main()
