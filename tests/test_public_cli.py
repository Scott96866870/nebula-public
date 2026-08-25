"""Tests for the public release metadata command."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
import unittest

from nebula_public.__main__ import main


class PublicCliTests(unittest.TestCase):
    def run_command(self, *args: str) -> dict[str, object]:
        stream = io.StringIO()
        with redirect_stdout(stream):
            status = main(args)
        self.assertEqual(status, 0)
        return json.loads(stream.getvalue())

    def test_default_info_is_read_only_metadata(self) -> None:
        payload = self.run_command()
        self.assertEqual(payload["name"], "Nebula Public Edition")
        self.assertEqual(payload["version"], "0.1.0")
        self.assertNotIn("excluded", payload)

    def test_catalog_describes_public_boundary(self) -> None:
        payload = self.run_command("catalog")
        self.assertIn("Public documentation", payload["included"])
        self.assertIn("Operational modules", payload["excluded"])


if __name__ == "__main__":
    unittest.main()
