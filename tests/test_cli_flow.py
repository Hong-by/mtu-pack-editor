from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliFlowTest(unittest.TestCase):
    def test_build_edits_only_existing_stat_rows(self) -> None:
        with self.subTest("build"):
            tmp_path = ROOT / "work" / "test-output"
            tmp_path.mkdir(parents=True, exist_ok=True)
            output = tmp_path / "output.pack"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tk_pack_builder",
                    "build",
                    "--recipe",
                    str(ROOT / "examples" / "recipe.effect-edit.json"),
                    "--input",
                    str(ROOT / "examples" / "starter.pack"),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            melee = {
                row["key"]: row
                for row in data["tables"]["melee_weapons"]
            }
            armour = {
                row["key"]: row
                for row in data["tables"]["unit_armour_types"]
            }
            projectiles = {
                row["key"]: row
                for row in data["tables"]["projectiles"]
            }
            self.assertEqual(melee["3k_mtu_general_2h175_comet_spear_unique"]["damage"], 25)
            self.assertEqual(melee["3k_mtu_hero_2h175_comet_spear_unique"]["damage"], 2015)
            self.assertEqual(armour["3k_mtu_hero_chen_jiu_unique"]["armour_value"], 70)
            self.assertEqual(projectiles["3k_mtu_hero_bow_hawk_unique"]["ap_damage"], 900)

    def test_validate_rejects_ambiguous_weapon_without_game_mode(self) -> None:
        tmp_path = ROOT / "work" / "test-output"
        tmp_path.mkdir(parents=True, exist_ok=True)
        recipe = tmp_path / "recipe.json"
        recipe.write_text(
            json.dumps(
                {
                    "modName": "bad_recipe",
                    "equipmentStatPatches": [
                        {
                            "equipmentKey": "3k_mtu_ancillary_weapon_comet_spear",
                            "statTable": "melee_weapon",
                            "column": "damage",
                            "value": 99,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tk_pack_builder",
                "validate",
                "--recipe",
                str(recipe),
                "--input",
                str(ROOT / "examples" / "starter.pack"),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("provide gameMode", result.stdout)

    def test_validate_rejects_equipment_creation_recipe(self) -> None:
        tmp_path = ROOT / "work" / "test-output"
        tmp_path.mkdir(parents=True, exist_ok=True)
        recipe = tmp_path / "create-equipment.json"
        recipe.write_text(
            json.dumps(
                {
                    "modName": "bad_recipe",
                    "newEquipment": [
                        {
                            "equipmentKey": "hby_new_sword"
                        }
                    ],
                    "equipmentStatPatches": [
                        {
                            "equipmentKey": "3k_mtu_ancillary_armour_chen_jius_armour_unique",
                            "statTable": "armour",
                            "column": "armour_value",
                            "value": 99,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tk_pack_builder",
                "validate",
                "--recipe",
                str(recipe),
                "--input",
                str(ROOT / "examples" / "starter.pack"),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("forbidden_equipment_operation", result.stdout)

    def test_read_table_uses_adapter_rows(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tk_pack_builder",
                "read-table",
                "--input",
                str(ROOT / "examples" / "starter.pack"),
                "--table",
                "melee_weapons",
                "--limit",
                "1",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["rowCount"], 2)
        self.assertEqual(len(payload["rows"]), 1)
        self.assertEqual(payload["rows"][0]["key"], "3k_mtu_general_2h175_comet_spear_unique")

    def test_read_table_can_use_vanilla_source(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tk_pack_builder",
                "read-table",
                "--input",
                str(ROOT / "examples" / "starter.pack"),
                "--source",
                "vanilla",
                "--table",
                "character_generation_spawn_age_ranges",
                "--limit",
                "1",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["source"], "vanilla")
        self.assertEqual(payload["rowCount"], 1)
        self.assertEqual(payload["rows"][0]["key"], "3k_main_age_fixed_historical_pang_de_hero_wood")

    def test_list_tables_can_use_vanilla_source(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tk_pack_builder",
                "list-tables",
                "--input",
                str(ROOT / "examples" / "starter.pack"),
                "--source",
                "vanilla",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["source"], "vanilla")
        self.assertIn("character_generation_spawn_age_ranges", payload["tables"])

    def test_build_in_place_updates_input_pack(self) -> None:
        tmp_path = ROOT / "work" / "test-output"
        tmp_path.mkdir(parents=True, exist_ok=True)
        input_pack = tmp_path / "in-place.pack"
        shutil.copyfile(ROOT / "examples" / "starter.pack", input_pack)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tk_pack_builder",
                "build",
                "--recipe",
                str(ROOT / "examples" / "recipe.effect-edit.json"),
                "--input",
                str(input_pack),
                "--in-place",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("pack_saved", result.stdout)
        data = json.loads(input_pack.read_text(encoding="utf-8"))
        melee = {row["key"]: row for row in data["tables"]["melee_weapons"]}
        self.assertEqual(melee["3k_mtu_general_2h175_comet_spear_unique"]["damage"], 25)

    def test_build_requires_one_save_mode(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tk_pack_builder",
                "build",
                "--recipe",
                str(ROOT / "examples" / "recipe.effect-edit.json"),
                "--input",
                str(ROOT / "examples" / "starter.pack"),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("Either --output", result.stdout)

    def test_build_clones_character_from_existing_rows(self) -> None:
        tmp_path = ROOT / "work" / "test-output"
        tmp_path.mkdir(parents=True, exist_ok=True)
        output = tmp_path / "character-clone.pack"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tk_pack_builder",
                "build",
                "--recipe",
                str(ROOT / "examples" / "recipe.character-clone.json"),
                "--input",
                str(ROOT / "examples" / "starter.pack"),
                "--output",
                str(output),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("1 cloned character", result.stdout)
        data = json.loads(output.read_text(encoding="utf-8"))
        templates = {row["key"]: row for row in data["tables"]["character_generation_templates"]}
        new_template = templates["hby_template_clone_chen_jiu_body_dong_min_art"]
        self.assertEqual(new_template["art_set_override"], "hby_art_set_clone_dong_min_general")
        self.assertEqual(new_template["spawn_age_range"], "hby_age_clone_chen_jiu")
        self.assertEqual(new_template["subtype"], "3k_general_earth")

        detail_rows = [
            row for row in data["tables"]["character_generation_template_game_mode_details"]
            if row["character_generation_template"] == "hby_template_clone_chen_jiu_body_dong_min_art"
        ]
        self.assertEqual(len(detail_rows), 2)
        self.assertTrue(all(row["initial_ceos"] == "hby_ceo_initial_data_clone_chen_jiu" for row in detail_rows))

        art_sets = {row["art_set_id"]: row for row in data["tables"]["campaign_character_art_sets"]}
        self.assertIn("hby_art_set_clone_dong_min_general", art_sets)
        arts = [
            row for row in data["tables"]["campaign_character_arts"]
            if row["art_set_id"] == "hby_art_set_clone_dong_min_general"
        ]
        self.assertEqual(len(arts), 1)
        self.assertEqual(arts[0]["portrait"], "3k_main_hero_special_earth_dong_min/")

        ages = {row["key"]: row for row in data["tables"]["character_generation_spawn_age_ranges"]}
        self.assertEqual(ages["hby_age_clone_chen_jiu"]["birth_year"], 172)

        ceos = {row["key"]: row for row in data["tables"]["ceo_initial_datas"]}
        self.assertIn("hby_ceo_initial_data_clone_chen_jiu", ceos)


if __name__ == "__main__":
    unittest.main()
