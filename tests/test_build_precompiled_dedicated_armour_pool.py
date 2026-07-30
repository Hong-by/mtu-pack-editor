from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tk_pack_builder.ceo_ccd import CeoCcd
from tk_pack_builder.dedicated_armour_pool import load_dedicated_armour_pools


ROOT = Path(__file__).resolve().parents[1]
VANILLA_CCD = ROOT / "work" / "dedicated_armour_poc" / "vanilla_base.ceo_data.ccd"
POC_CCD = (
    ROOT
    / "tk_pack_builder"
    / "data"
    / "dedicated_armour_pools"
    / "vanilla-poc-mulu-001.ccd"
)
TEMPLATE = (
    ROOT
    / "tk_pack_builder"
    / "data"
    / "dedicated_armour_pools"
    / "vanilla-poc-mulu-001.json"
)


@unittest.skipUnless(
    VANILLA_CCD.is_file() and POC_CCD.is_file(),
    "local Assembly Kit POC fixtures are unavailable",
)
class BuildPrecompiledDedicatedArmourPoolTest(unittest.TestCase):
    def test_builds_fingerprint_gated_wildcard_pool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "pool"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "build_precompiled_dedicated_armour_pool.py"),
                    "--base-ccd",
                    str(VANILLA_CCD),
                    "--augmented-ccd",
                    str(POC_CCD),
                    "--target-ccd",
                    str(VANILLA_CCD),
                    "--template-manifest",
                    str(TEMPLATE),
                    "--output-dir",
                    str(output_dir),
                    "--pool-id",
                    "test-precompiled-pool",
                    "--label",
                    "Test pool",
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            report = json.loads(result.stdout)
            self.assertTrue(report["ok"])
            self.assertEqual(report["mergeStats"]["groupsAdded"], 13)

            pool = load_dedicated_armour_pools([output_dir])[0]
            self.assertEqual(pool.mode, "precompiled")
            self.assertEqual(pool.slots[0].source_ceo_key, "*")
            compiled = CeoCcd.from_path(pool.ccd_path)
            self.assertIn(
                "hby_poc_ancillary_armour_mulu_dedicated_001",
                set(compiled.all_strings()),
            )


if __name__ == "__main__":
    unittest.main()
