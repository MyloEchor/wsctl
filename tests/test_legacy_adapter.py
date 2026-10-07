from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from wsctl.adapters.legacy_workspace import run_legacy_json


class LegacyJsonBridgeTest(unittest.TestCase):
    def test_bridge_sanitizes_dates_and_preserves_semantic_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "tools" / "wsctl" / "src" / "wsctl"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("", encoding="utf-8")
            (package / "io.py").write_text(
                textwrap.dedent(
                    """
                    import json

                    def dump_json(data):
                        return json.dumps(data)
                    """
                ),
                encoding="utf-8",
            )
            (package / "cli.py").write_text(
                textwrap.dedent(
                    """
                    import datetime
                    import sys
                    from .io import dump_json

                    def main(argv):
                        print(dump_json({
                            "ok": True,
                            "when": datetime.date(2026, 10, 8),
                            "args": argv,
                        }))
                        return 1 if "--semantic-failure" in argv else 0
                    """
                ),
                encoding="utf-8",
            )

            result = run_legacy_json(root, ["doctor", "--semantic-failure", "--json"])
            self.assertTrue(result["ok"])
            self.assertEqual("2026-10-08", result["when"])
            self.assertEqual(1, result["_legacy_exit_code"])


if __name__ == "__main__":
    unittest.main()

