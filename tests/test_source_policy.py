from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tk_pack_builder import web
from tk_pack_builder.internal_materials import MaterialPackSession
from tk_pack_builder.source_policy import (
    REFERENCE_PACK, require_clean_materials, require_clean_references,
    require_supported_sources, supported_source,
)


class SourcePolicyTest(unittest.TestCase):
    def test_only_supported_reference_sources(self):
        require_supported_sources([Path("database.pack"), Path("my_hero.pack"), Path(REFERENCE_PACK)])
        for name in ("mtu_reference_core.pack", "!!190expande_korea_addon.pack", "BFG_Originals.pack", "arbitrary.pack"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                require_supported_sources([Path(name)])
        self.assertTrue(supported_source(r"E:\old\data_ep.pack"))

    def test_old_snapshot_rejected_even_when_tables_look_vanilla(self):
        with self.assertRaisesRegex(ValueError, "외부 모드"):
            require_clean_materials({"sources": [r"E:\old\!!190expande_korea_addon.pack"], "tables": {}})

    def test_foreign_rows_in_allowed_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "모드 참조"):
            require_clean_materials({"sources": ["database.pack"], "tables": {
                "db/character_generation_templates_tables/data__": {
                    "sourcePath": "database.pack", "rows": [{"key": "ironic_template_foo"}],
                },
            }})

    def test_old_queue_blocked_before_open_or_write(self):
        payload = {"recipe": {"characterClones": [{"sourceTemplateKey": "3k_mod_template_historical_foo"}]}}
        with patch.object(web, "_open_session") as open_session:
            for operation in (web.validate_payload, web.build_payload):
                with self.assertRaisesRegex(ValueError, "다시 선택"):
                    operation(payload)
            open_session.assert_not_called()

    def test_default_reference_is_clean_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            refs = root / "work" / "packs" / "refs"
            refs.mkdir(parents=True)
            (refs / REFERENCE_PACK).touch()
            (refs / "mtu_reference_core.pack").touch()
            with patch.object(web, "ROOT", root), patch.object(web, "default_game_local_pack_paths", return_value=[]):
                self.assertEqual(web._reference_pack_paths({}), [(refs / REFERENCE_PACK).resolve()])

    def test_clean_materials_readable_and_foreign_nested_reference_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps({"sources": ["my_hero.pack"], "tables": {}}), encoding="utf-8")
            self.assertEqual(MaterialPackSession.open(path).list_tables(), [])
        with self.assertRaises(ValueError):
            require_clean_references({"workItems": [{"details": {"initial_ceos": "ironic_ceo_foo"}}]})

    def test_ui_has_no_korea_faction_filters(self):
        html = (web.STATIC_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('data-filter="korea:', html)
        self.assertIn(REFERENCE_PACK, html)
        self.assertIn("바닐라·MTU", html)


if __name__ == "__main__":
    unittest.main()
