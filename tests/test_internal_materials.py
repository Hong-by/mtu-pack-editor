from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tk_pack_builder.internal_materials import MaterialPackSession


class MaterialPackSessionTest(unittest.TestCase):
    def test_reads_tables_locs_and_metadata(self) -> None:
        payload = {
            "baseline": "v0.1.5",
            "tables": {
                "db/example_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "row_a", "value": 10}],
                }
            },
            "loc": {
                "text/db/example.loc": {
                    "rows": {"example_key": "예시"}
                }
            },
            "assets": {
                "ui/characters/example/stills/unitcards/example.png": {
                    "sourcePath": "example.pack"
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            session = MaterialPackSession.open(path)

        self.assertEqual(session.list_tables(), ["db/example_tables/data__"])
        self.assertEqual(session.read_table("example"), [{"key": "row_a", "value": 10}])
        self.assertIn("db/example_tables/data__", session.decoded_db_by_path)
        self.assertEqual(session.list_loc_files(), ["text/db/example.loc"])
        self.assertEqual(session.read_loc("text/db/example.loc"), {"example_key": "예시"})
        self.assertEqual(session.list_files(), ["ui/characters/example/stills/unitcards/example.png"])
        self.assertEqual(session.metadata()["adapter"], "internal-materials")

    def test_rejects_ambiguous_short_table_name(self) -> None:
        payload = {
            "tables": {
                "db/example_tables/a": {"rows": []},
                "db/example_tables/b": {"rows": []},
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        with self.assertRaisesRegex(ValueError, "ambiguous"):
            session.read_table("example")

    def test_prefers_vanilla_attribute_material_tables(self) -> None:
        payload = {
            "tables": {
                "db/character_attribute_sets_tables/data": {
                    "rows": [{"set_name": "custom_set"}],
                },
                "db/character_attribute_sets_tables/data__": {
                    "rows": [{"set_name": "3k_main_attribute_set_general_water_records"}],
                },
                "db/character_attributes_tables/data": {
                    "rows": [{"set_name": "custom_set", "attribute_type": "authority"}],
                },
                "db/character_attributes_tables/data__": {
                    "rows": [{"set_name": "3k_main_attribute_set_general_water_records", "attribute_type": "authority"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        self.assertEqual(
            session.read_table("character_attribute_sets"),
            [{"set_name": "3k_main_attribute_set_general_water_records"}],
        )
        self.assertEqual(
            session.read_table("character_attributes"),
            [{"set_name": "3k_main_attribute_set_general_water_records", "attribute_type": "authority"}],
        )


if __name__ == "__main__":
    unittest.main()
