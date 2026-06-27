from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tk_pack_builder import delta_builder


class DeltaBuilderAssetTest(unittest.TestCase):
    def test_find_extracted_asset_prefers_core_source(self) -> None:
        original_root = delta_builder.EXTRACTED_ASSET_ROOT
        original_core = delta_builder.CORE_ASSET_SOURCE_ID
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                packed_path = "ui/characters/example/stills/unitcards/example.png"
                fallback = root / "fallback" / packed_path
                core = root / "core" / packed_path
                fallback.parent.mkdir(parents=True, exist_ok=True)
                core.parent.mkdir(parents=True, exist_ok=True)
                fallback.write_bytes(b"fallback")
                core.write_bytes(b"core")

                delta_builder.EXTRACTED_ASSET_ROOT = root
                delta_builder.CORE_ASSET_SOURCE_ID = "core"

                found = delta_builder._find_extracted_asset(packed_path)

                self.assertIsNotNone(found)
                self.assertEqual(found.read_bytes(), b"core")
        finally:
            delta_builder.EXTRACTED_ASSET_ROOT = original_root
            delta_builder.CORE_ASSET_SOURCE_ID = original_core

    def test_copy_extracted_asset_can_rename_destination_path(self) -> None:
        original_root = delta_builder.EXTRACTED_ASSET_ROOT
        original_core = delta_builder.CORE_ASSET_SOURCE_ID

        class FakeClient:
            def __init__(self) -> None:
                self.request = None

            def send(self, request):
                self.request = request
                dest_paths = request["AddPackedFiles"][2]
                return {"response": "Success", "data": {"VecContainerPathOptionString": [dest_paths, None]}}

        class FakeSession:
            def __init__(self) -> None:
                self.client = FakeClient()

        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = "ui/characters/source/stills/unitcards/source.png"
                target = "ui/characters/target/stills/unitcards/target.png"
                asset = root / "core" / source
                asset.parent.mkdir(parents=True, exist_ok=True)
                asset.write_bytes(b"image")
                delta_builder.EXTRACTED_ASSET_ROOT = root
                delta_builder.CORE_ASSET_SOURCE_ID = "core"

                session = FakeSession()
                copied, missing = delta_builder._copy_available_extracted_image_assets(
                    session,
                    "target.pack",
                    [(source, target)],
                )

            self.assertEqual(copied, 1)
            self.assertEqual(missing, [])
            self.assertEqual(session.client.request["AddPackedFiles"][2], [{"File": target}])
        finally:
            delta_builder.EXTRACTED_ASSET_ROOT = original_root
            delta_builder.CORE_ASSET_SOURCE_ID = original_core

    def test_image_asset_target_must_match_art_override_token(self) -> None:
        class Clone:
            new_template_key = "hby_template_test"
            art_overrides = {"portrait": "hby_hero_test/", "card": "hby_hero_test"}
            image_assets = [{
                "path": "ui/characters/source/stills/unitcards/source.png",
                "targetPath": "ui/characters/hby_template_test/stills/unitcards/hby_hero_test.png",
            }]

        with self.assertRaisesRegex(ValueError, "does not match"):
            delta_builder._validate_clone_image_asset_targets([Clone()])


if __name__ == "__main__":
    unittest.main()
