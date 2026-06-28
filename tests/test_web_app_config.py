from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WebAppConfigTest(unittest.TestCase):
    def test_internal_materials_build_is_enabled_for_patch_pack(self) -> None:
        app_js = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        match = re.search(r"enabledForSaveMode:\s*'([^']*)'", app_js)

        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "patch_pack")


if __name__ == "__main__":
    unittest.main()
