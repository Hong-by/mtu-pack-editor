from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tk_pack_builder import web
from tk_pack_builder.validation import ValidationMessage


class FakeSession:
    pack_path = Path("writer.pack")
    pack_key = "writer.pack"

    def close(self) -> None:
        return None


class WebMaterialBuildTest(unittest.TestCase):
    def test_build_payload_uses_internal_materials_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            materials = tmp_path / "materials.json"
            materials.write_text(json.dumps({"tables": {}, "loc": {}, "assets": {}}), encoding="utf-8")
            output = tmp_path / "out.pack"
            output.write_bytes(b"pack")
            with (
                patch.object(web, "_open_session", return_value=FakeSession()) as open_session,
                patch.object(web.delta_builder_module, "build_delta_pack_from_materials", return_value=[{"level": "success", "code": "ok", "message": "built"}]) as build,
            ):
                previous_core = web.delta_builder_module.CORE_ASSET_SOURCE_ID
                result = web.build_payload({
                    "adapter": "rpfm",
                    "inputPath": "writer.pack",
                    "outputPath": str(output),
                    "delta": True,
                    "useInternalMaterials": True,
                    "materialPath": str(materials),
                    "coreAssetSourceId": "core-test",
                    "recipe": {"modName": "test"},
                })

        self.assertTrue(result["ok"])
        self.assertEqual(result["messages"], [{"level": "success", "code": "pack_written", "message": "팩 생성 완료"}])
        self.assertEqual(web.delta_builder_module.CORE_ASSET_SOURCE_ID, previous_core)
        open_session.assert_called_once()
        build.assert_called_once()

    def test_internal_materials_requires_patch_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            materials = Path(tmp) / "materials.json"
            materials.write_text(json.dumps({"tables": {}, "loc": {}, "assets": {}}), encoding="utf-8")
            with patch.object(web, "_open_session", return_value=FakeSession()):
                with self.assertRaisesRegex(ValueError, "only available for patch pack"):
                    web.build_payload({
                        "adapter": "rpfm",
                        "inputPath": "writer.pack",
                        "outputPath": str(Path(tmp) / "out.pack"),
                        "delta": False,
                        "useInternalMaterials": True,
                        "materialPath": str(materials),
                        "recipe": {"modName": "test"},
                    })

    def test_validate_payload_uses_internal_materials_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            materials = Path(tmp) / "materials.json"
            materials.write_text(json.dumps({"tables": {}, "loc": {}, "assets": {}}), encoding="utf-8")
            expected_messages = [ValidationMessage("success", "ok", "validated")]

            with (
                patch.object(web, "_open_session") as open_session,
                patch.object(web, "validate", return_value=expected_messages) as validate_mock,
            ):
                result = web.validate_payload({
                    "adapter": "rpfm",
                    "inputPath": "writer.pack",
                    "outputPath": str(Path(tmp) / "out.pack"),
                    "delta": True,
                    "useInternalMaterials": True,
                    "materialPath": str(materials),
                    "recipe": {"modName": "test"},
                })

        self.assertTrue(result["ok"])
        self.assertEqual(result["messages"], [{"level": "success", "code": "ok", "message": "validated"}])
        open_session.assert_not_called()
        self.assertEqual(validate_mock.call_args.args[0].metadata()["adapter"], "internal-materials")


if __name__ == "__main__":
    unittest.main()
