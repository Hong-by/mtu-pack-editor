from __future__ import annotations

import unittest

from tk_pack_builder.web import _build_asset_index, _character_image_assets, _find_character_panel_image


class WebImageAssetsTest(unittest.TestCase):
    def test_character_image_assets_include_stills_when_preview_is_composite(self) -> None:
        paths = [
            "ui/characters/hero_folder/composites/large_panel/norm/noanim.png",
            "ui/characters/hero_folder/composites/small_panel/norm/noanim.png",
            "ui/characters/hero_folder/stills/halfbody_large/SAD_hero_card.png",
            "ui/characters/hero_folder/stills/unitcards/SAD_hero_card.png",
        ]
        asset_index = _build_asset_index(paths)
        asset_sources = {path: "source.pack" for path in paths}

        assets = _character_image_assets(
            asset_index,
            asset_sources,
            "hero_folder/",
            "SAD_hero_card",
        )
        asset_paths = {asset["path"] for asset in assets}

        self.assertIn("ui/characters/hero_folder/composites/large_panel/norm/noanim.png", asset_paths)
        self.assertIn("ui/characters/hero_folder/stills/halfbody_large/SAD_hero_card.png", asset_paths)
        self.assertIn("ui/characters/hero_folder/stills/unitcards/SAD_hero_card.png", asset_paths)

    def test_panel_preview_prefers_large_panel_over_halfbody(self) -> None:
        paths = [
            "ui/characters/hero_folder/stills/halfbody_large/hero_folder.png",
            "ui/characters/hero_folder/composites/large_panel/norm/noanim.png",
        ]
        asset_index = _build_asset_index(paths)

        self.assertEqual(
            _find_character_panel_image(asset_index, "hero_folder/"),
            "ui/characters/hero_folder/composites/large_panel/norm/noanim.png",
        )


if __name__ == "__main__":
    unittest.main()
