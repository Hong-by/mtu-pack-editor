from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tk_pack_builder.asset_manifest import (
    assets_under_character_root,
    build_asset_manifest,
    character_asset_root,
    find_character_image_path,
    inventory_asset_files,
)


class AssetManifestTest(unittest.TestCase):
    def test_character_root_collects_composites_and_stills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset_root = root / "assets"
            source = asset_root / "source_a"
            paths = [
                "ui/characters/hero_a/composites/large_panel/norm/noanim.png",
                "ui/characters/hero_a/stills/halfbody_large/hero_a.png",
                "ui/characters/hero_a/stills/unitcards/hero_a.png",
                "ui/characters/hero_b/stills/unitcards/hero_b.png",
            ]
            for path in paths:
                target = source / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.encode("utf-8"))

            assets = inventory_asset_files(asset_root)
            assets_by_path = {}
            for asset in assets:
                assets_by_path.setdefault(asset.packed_path.lower(), []).append(asset)

            preview = find_character_image_path(assets_by_path, "hero_a", "halfbody_large")
            self.assertEqual(preview, "ui/characters/hero_a/stills/halfbody_large/hero_a.png")
            root_path = character_asset_root(preview or "")
            self.assertEqual(root_path, "ui/characters/hero_a")
            collected = assets_under_character_root(assets_by_path, root_path or "")

        self.assertEqual(len(collected), 3)
        self.assertTrue(all(asset.packed_path.startswith("ui/characters/hero_a/") for asset in collected))

    def test_manifest_uses_only_unique_character_reachable_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            materials = {
                "baseline": "v0.1.5",
                "tables": {
                    "db/character_generation_templates_tables/_mtu_characters": {
                        "rows": [
                            {"key": "unique_a", "unique": True, "art_set_override": "art_a"},
                            {"key": "non_unique_b", "unique": False, "art_set_override": "art_b"},
                        ]
                    },
                    "db/campaign_character_arts_tables/_mtu_characters": {
                        "rows": [
                            {
                                "art_set_id": "art_a",
                                "portrait": "hero_a/",
                                "card": "hero_a",
                                "has_come_of_age": True,
                            },
                            {
                                "art_set_id": "art_b",
                                "portrait": "hero_b/",
                                "card": "hero_b",
                                "has_come_of_age": True,
                            },
                        ]
                    },
                },
            }
            materials_path = root / "materials.json"
            materials_path.write_text(json.dumps(materials), encoding="utf-8")
            asset_root = root / "assets"
            for path in [
                "ui/characters/hero_a/stills/halfbody_large/hero_a.png",
                "ui/characters/hero_a/composites/large_panel/norm/noanim.png",
                "ui/characters/hero_b/stills/halfbody_large/hero_b.png",
            ]:
                target = asset_root / "source_a" / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.encode("utf-8"))

            manifest = build_asset_manifest(materials_path, asset_root, [])

        self.assertEqual(manifest["summary"]["uniqueCharacterCount"], 1)
        self.assertEqual(manifest["uniqueCharacterAssets"]["unique_a"]["assetCount"], 2)
        self.assertNotIn("non_unique_b", manifest["uniqueCharacterAssets"])


if __name__ == "__main__":
    unittest.main()
