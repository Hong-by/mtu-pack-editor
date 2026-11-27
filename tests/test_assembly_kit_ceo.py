from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from tk_pack_builder.assembly_kit_ceo import (
    DedicatedArmourCeoRequest,
    build_dedicated_armour_ceo_plan,
)


def _write_table(
    directory: Path,
    table_name: str,
    rows: list[dict[str, object]],
) -> None:
    root = ET.Element("dataroot")
    for row in rows:
        element = ET.SubElement(root, table_name)
        for key, value in row.items():
            child = ET.SubElement(element, key)
            child.text = str(value)
    ET.ElementTree(root).write(
        directory / f"{table_name}.xml",
        encoding="utf-8",
        xml_declaration=True,
    )


class DedicatedArmourCeoPlanTest(unittest.TestCase):
    def test_clones_ceo_stats_effects_and_initial_equipment_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            db_dir = Path(temporary_directory)
            fixture = {
                "ceos": [{"key": "source_armour", "category": "armour"}],
                "ceos_to_equipment_variants": [
                    {"ceos_key": "source_armour", "armour": "source_armour_type"}
                ],
                "unit_armour_types": [
                    {"key": "source_armour_type", "armour_value": "44", "audio_type": "Leather"}
                ],
                "ceo_effect_lists": [{"key": "source_armour"}],
                "ceo_effect_list_to_effects": [
                    {"auto_id": "1", "effect_list": "source_armour", "effect": "effect_a"}
                ],
                "ceo_group_ceos": [
                    {"auto_id": "2", "ceo": "source_armour", "group": "armour_group"}
                ],
                "ceo_nodes": [
                    {"key": "source_armour", "ceo_effect_list": "source_armour"}
                ],
                "ceo_thresholds": [{"key": "source_armour", "ceo": "source_armour"}],
                "ceo_threshold_nodes": [
                    {
                        "auto_id": "3",
                        "ceo_node": "source_armour",
                        "ceo_threshold": "source_armour",
                    }
                ],
                "ceo_initial_datas": [
                    {"key": "source_initial", "template_manager": "character_ceo_manager"}
                ],
                "ceo_initial_data_stages": [{"key": "source_equipment_stage"}],
                "ceo_initial_data_to_stages": [
                    {
                        "ceo_initial_data": "source_initial",
                        "initial_data_stage": "shared_trait_stage",
                        "stage": "1",
                    },
                    {
                        "ceo_initial_data": "source_initial",
                        "initial_data_stage": "source_equipment_stage",
                        "stage": "2",
                    },
                ],
                "ceo_initial_data_equipments": [
                    {
                        "auto_id": "4",
                        "category": "3k_main_ceo_category_ancillary_armour",
                        "equipped_ceo": "source_armour",
                        "initial_data_stage": "source_equipment_stage",
                        "slot_index": "0",
                        "target": "character_equipment",
                    },
                    {
                        "auto_id": "5",
                        "category": "3k_main_ceo_category_ancillary_weapon",
                        "equipped_ceo": "source_weapon",
                        "initial_data_stage": "source_equipment_stage",
                        "slot_index": "0",
                        "target": "character_equipment",
                    },
                ],
                "ceo_initial_data_active_ceos": [
                    {
                        "auto_id": "6",
                        "active_ceo": "source_armour",
                        "initial_data_stage": "source_equipment_stage",
                        "starting_points_delta": "0",
                    }
                ],
                "ceo_initial_data_active_spawners": [],
                "ceo_initial_data_triggers": [],
                "ceo_initial_data_scripted_permissions": [],
            }
            for table_name, rows in fixture.items():
                _write_table(db_dir, table_name, rows)

            request = DedicatedArmourCeoRequest(
                source_ceo_key="source_armour",
                source_initial_ceo_key="source_initial",
                new_ceo_key="new_armour",
                new_initial_ceo_key="new_initial",
                new_armour_type_key="new_armour_type",
                new_equipment_stage_key="new_equipment_stage",
                armour_value=77,
            )
            plan = build_dedicated_armour_ceo_plan(db_dir, request)

        self.assertLess(
            list(plan.tables).index("unit_armour_types"),
            list(plan.tables).index("ceos_to_equipment_variants"),
        )
        self.assertEqual(
            plan.tables["unit_armour_types"],
            [{"key": "new_armour_type", "armour_value": "77", "audio_type": "Leather"}],
        )
        self.assertEqual(
            plan.tables["ceos_to_equipment_variants"][0]["armour"],
            "new_armour_type",
        )
        self.assertEqual(
            plan.tables["ceo_initial_data_equipments"][0]["equipped_ceo"],
            "new_armour",
        )
        self.assertEqual(
            plan.tables["ceo_initial_data_active_ceos"][0]["active_ceo"],
            "new_armour",
        )
        self.assertEqual(
            {
                row["initial_data_stage"]
                for row in plan.tables["ceo_initial_data_to_stages"]
            },
            {"shared_trait_stage", "new_equipment_stage"},
        )
        self.assertEqual(plan.tables["ceo_nodes"][0]["key"], "new_armour")
        self.assertEqual(
            plan.tables["ceo_effect_list_to_effects"][0]["effect_list"],
            "new_armour",
        )


if __name__ == "__main__":
    unittest.main()
