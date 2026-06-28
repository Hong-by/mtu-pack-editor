from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tk_pack_builder import delta_builder


class DeltaBuilderAssetTest(unittest.TestCase):
    def png_bytes(self, comment: str | None = None) -> bytes:
        chunks = [
            delta_builder._png_chunk(b"IHDR", b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"),
        ]
        if comment is not None:
            chunks.append(delta_builder._png_chunk(b"tEXt", b"Comment\x00" + comment.encode("latin1")))
        chunks.extend([
            delta_builder._png_chunk(b"IDAT", b"x\x9cc``\x00\x00\x00\x04\x00\x01"),
            delta_builder._png_chunk(b"IEND", b""),
        ])
        return delta_builder.PNG_SIGNATURE + b"".join(chunks)

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

    def test_find_extracted_asset_prefers_explicit_source_path_for_retarget(self) -> None:
        original_root = delta_builder.EXTRACTED_ASSET_ROOT
        original_core = delta_builder.CORE_ASSET_SOURCE_ID
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                packed_path = "ui/characters/example/composites/large_panel/norm/norm.png"
                stale = root / "stale_backup" / packed_path
                source_root = root / "fresh_source"
                fresh = source_root / packed_path
                stale.parent.mkdir(parents=True, exist_ok=True)
                fresh.parent.mkdir(parents=True, exist_ok=True)
                stale.write_bytes(b"stale")
                fresh.write_bytes(b"fresh")

                delta_builder.EXTRACTED_ASSET_ROOT = root
                delta_builder.CORE_ASSET_SOURCE_ID = "missing_core"

                found = delta_builder._find_extracted_asset(packed_path, str(source_root))

                self.assertIsNotNone(found)
                self.assertEqual(found.read_bytes(), b"fresh")
        finally:
            delta_builder.EXTRACTED_ASSET_ROOT = original_root
            delta_builder.CORE_ASSET_SOURCE_ID = original_core

    def test_find_extracted_asset_accepts_panel_path_without_composites(self) -> None:
        original_root = delta_builder.EXTRACTED_ASSET_ROOT
        original_core = delta_builder.CORE_ASSET_SOURCE_ID
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source_root = root / "fresh_source"
                requested = "ui/characters/example/large_panel/norm/norm.png"
                actual = source_root / "ui/characters/example/composites/large_panel/norm/norm.png"
                actual.parent.mkdir(parents=True, exist_ok=True)
                actual.write_bytes(b"panel")

                delta_builder.EXTRACTED_ASSET_ROOT = root
                delta_builder.CORE_ASSET_SOURCE_ID = "missing_core"

                found = delta_builder._find_extracted_asset(requested, str(source_root))

                self.assertIsNotNone(found)
                self.assertEqual(found.read_bytes(), b"panel")
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

    def test_prepare_image_asset_adds_panel_comment_when_missing(self) -> None:
        class FakeSession:
            def read_file_bytes(self, packed_path: str) -> bytes:
                raise ValueError("not found")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.png"
            path.write_bytes(self.png_bytes())

            prepared = delta_builder._prepare_image_asset_for_pack(
                FakeSession(),
                path,
                "ui/characters/example/composites/small_panel/norm/norm.png",
            )

            self.assertNotEqual(prepared, path)
            comment = delta_builder._png_text_chunk(prepared.read_bytes(), "Comment")
            self.assertEqual(
                comment,
                "[type:norm;x:-7;y:84;z-order:0;pivot_x:0.4997;pivot_y:0.4996;]",
            )

    def test_prepare_image_asset_prefers_existing_target_comment(self) -> None:
        target_comment = "[type:norm;x:-15;y:102;z-order:0;pivot_x:0.4997;pivot_y:0.5000;]"

        class FakeSession:
            def read_file_bytes(self, packed_path: str) -> bytes:
                return DeltaBuilderAssetTest().png_bytes(target_comment)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.png"
            path.write_bytes(self.png_bytes("[type:norm;x:-7;y:84;z-order:0;pivot_x:0.4997;pivot_y:0.4996;]"))

            prepared = delta_builder._prepare_image_asset_for_pack(
                FakeSession(),
                path,
                "ui/characters/example/composites/small_panel/norm/norm.png",
            )

            self.assertEqual(delta_builder._png_text_chunk(prepared.read_bytes(), "Comment"), target_comment)


if __name__ == "__main__":
    unittest.main()
