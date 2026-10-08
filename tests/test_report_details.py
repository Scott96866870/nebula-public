"""Regression coverage for actionable, literal Markdown report details."""

from contextlib import redirect_stdout
from dataclasses import replace
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nebula_public.__main__ import main
from nebula_public.audit import AuditReport, AuditViolation
from nebula_public.manifest import build_manifest
from nebula_public.report import ExtensionSummary, build_release_report


class ReportDetailsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "docs").mkdir()
        for name in ("README.md", "pyproject.toml", "docs/PUBLIC_SCOPE.md"):
            (self.root / name).write_text("public", encoding="utf-8")

    def test_boundary_details_preserve_case_and_explain_missing_files(self) -> None:
        (self.root / "CONFIG.JSON").write_text("private contents", encoding="utf-8")
        (self.root / "README.md").unlink()
        output = build_release_report(self.root).to_markdown()
        self.assertIn("**Status:** ACTION REQUIRED", output)
        self.assertIn("## Boundary violations", output)
        self.assertIn(r"- CONFIG\.JSON: blocked file pattern", output)
        self.assertIn(r"- README\.md: required public file is missing", output)
        self.assertNotIn("private contents", output)

    def test_cli_integrity_failures_include_each_category_and_counts(self) -> None:
        (self.root / "removed.txt").write_text("old", encoding="utf-8")
        manifest_path = self.root / "manifest.json"
        manifest_path.write_text(
            build_manifest(self.root, exclude=(manifest_path,)).to_json(),
            encoding="utf-8",
        )
        (self.root / "removed.txt").unlink()
        (self.root / "README.md").write_text("changed", encoding="utf-8")
        (self.root / "new.txt").write_text("new", encoding="utf-8")
        outputs = {}
        for format_name in ("markdown", "json"):
            stream = io.StringIO()
            with redirect_stdout(stream):
                status = main(("report", "--path", str(self.root), "--manifest",
                               str(manifest_path), "--format", format_name))
            self.assertEqual(status, 1)
            outputs[format_name] = stream.getvalue()
        output = outputs["markdown"]
        self.assertIn("**Expected files:** 4", output)
        self.assertIn("**Actual files:** 4", output)
        self.assertIn("### Missing\n\n- removed\\.txt", output)
        self.assertIn("### Modified\n\n- README\\.md", output)
        self.assertIn("### Unexpected\n\n- new\\.txt", output)
        integrity = json.loads(outputs["json"])["integrity"]
        self.assertEqual(integrity["missing"], ["removed.txt"])
        self.assertEqual(integrity["modified"], ["README.md"])
        self.assertEqual(integrity["unexpected"], ["new.txt"])

    def test_passing_integrity_has_explicit_empty_categories(self) -> None:
        report = build_release_report(self.root, manifest=build_manifest(self.root))
        output = report.to_markdown()
        self.assertIn("**Status:** READY", output)
        self.assertNotIn("## Boundary violations", output)
        for heading in ("Missing", "Modified", "Unexpected"):
            self.assertIn(f"### {heading}\n\n- None", output)
        self.assertEqual(output, report.to_markdown())

    def test_without_manifest_omits_integrity_details(self) -> None:
        output = build_release_report(self.root).to_markdown()
        self.assertIn("- Manifest integrity: not requested", output)
        self.assertNotIn("## Manifest integrity details", output)

    def test_markup_and_control_characters_remain_literal(self) -> None:
        path = "[link](https://example.test)/`<img>_&\n# title\t\x00\x7f"
        reason = "<b>reason</b>\r\n- injected"
        report = replace(
            build_release_report(self.root),
            boundary=AuditReport(str(self.root), 1, (AuditViolation(path, reason),)),
            extensions=(ExtensionSummary(".<img>`*", 1, 2),),
        )
        output = report.to_markdown()
        details = output.split("## Boundary violations\n\n")[1].split("\n\n")[0]
        self.assertEqual(len(details.splitlines()), 1)
        self.assertIn(r"\[link\]\(https://example\.test\)", details)
        self.assertIn(r"\`&lt;img&gt;\_&amp;\\x0a\# title\\x09\\x00\\x7f", details)
        self.assertIn(r"&lt;b&gt;reason&lt;/b&gt;\\x0d\\x0a\- injected", details)
        self.assertIn(r"- \.&lt;img&gt;\`\*: 1 file(s), 2 bytes", output)
        self.assertNotIn("<img>", output)
        self.assertEqual(report.to_dict()["boundary"]["violations"][0]["path"], path)


if __name__ == "__main__":
    unittest.main()
