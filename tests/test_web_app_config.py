from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WebAppConfigTest(unittest.TestCase):
    def test_patch_pack_uses_input_pack_by_default(self) -> None:
        app_js = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        match = re.search(r"enabledForSaveMode:\s*'([^']*)'", app_js)

        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "")


if __name__ == "__main__":
    unittest.main()
