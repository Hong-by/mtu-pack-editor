from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from tk_pack_builder.stat_tables import (
    _equipment_key_spellings,
    _find_variant,
    _find_variant_any,
    _require_row_with_table,
    resolve_stat_target,
)


def _mock_session(tables: dict[str, list[dict]]) -> Any:
    session = MagicMock()
    session.list_tables.return_value = list(tables.keys())
    session.read_table.side_effect = lambda name, source="pack": tables.get(name, [])
    return session


class EquipmentKeySpellingsTest(unittest.TestCase):
    def test_ancillary_spelling_adds_ancilliary_variant(self) -> None:
        spellings = _equipment_key_spellings("3k_mtu_ancillary_weapon_x")
        self.assertIn("3k_mtu_ancillary_weapon_x", spellings)
        self.assertIn("3k_mtu_ancilliary_weapon_x", spellings)

    def test_ancilliary_spelling_adds_ancillary_variant(self) -> None:
        spellings = _equipment_key_spellings("3k_mtu_ancilliary_weapon_x")
        self.assertIn("3k_mtu_ancilliary_weapon_x", spellings)
        self.assertIn("3k_mtu_ancillary_weapon_x", spellings)

    def test_key_without_ancill_stays_single(self) -> None:
        spellings = _equipment_key_spellings("3k_mtu_generic_key")
        self.assertEqual(spellings, ["3k_mtu_generic_key"])

    def test_no_duplicates_in_output(self) -> None:
        spellings = _equipment_key_spellings("some_key")
        self.assertEqual(len(spellings), len(set(spellings)))


class FindVariantTest(unittest.TestCase):
    def _rows(self) -> list[dict]:
        return [
            {"ceos_key": "key_a", "primary_melee_weapon": "weapon_a_hist", "game_mode": "historical"},
            {"ceos_key": "key_a", "primary_melee_weapon": "weapon_a_rom", "game_mode": "romance"},
            {"ceos_key": "key_b", "primary_melee_weapon": "weapon_b", "game_mode": "historical"},
        ]

    def test_finds_single_match_without_game_mode(self) -> None:
        rows = [{"ceos_key": "key_b", "primary_melee_weapon": "weapon_b", "game_mode": "historical"}]
        result = _find_variant(rows, "key_b", None, "primary_melee_weapon")
        self.assertEqual(result["primary_melee_weapon"], "weapon_b")

    def test_filters_by_game_mode(self) -> None:
        result = _find_variant(self._rows(), "key_a", "historical", "primary_melee_weapon")
        self.assertEqual(result["primary_melee_weapon"], "weapon_a_hist")

    def test_raises_when_not_found(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _find_variant(self._rows(), "key_missing", None, "primary_melee_weapon")
        self.assertIn("Equipment stat mapping not found", str(ctx.exception))

    def test_raises_when_ambiguous_without_game_mode(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _find_variant(self._rows(), "key_a", None, "primary_melee_weapon")
        self.assertIn("gameMode", str(ctx.exception))

    def test_raises_with_game_mode_info_when_not_found(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _find_variant(self._rows(), "key_a", "nonexistent_mode", "primary_melee_weapon")
        self.assertIn("nonexistent_mode", str(ctx.exception))

    def test_skips_row_with_empty_stat_key_field(self) -> None:
        rows = [{"ceos_key": "key_a", "primary_melee_weapon": "", "game_mode": "historical"}]
        with self.assertRaises(ValueError):
            _find_variant(rows, "key_a", None, "primary_melee_weapon")


class FindVariantAnyTest(unittest.TestCase):
    def test_falls_through_to_second_spelling(self) -> None:
        rows = [{"ceos_key": "key_ancilliary", "armour": "armour_row", "game_mode": "historical"}]
        result = _find_variant_any(rows, ["key_ancillary", "key_ancilliary"], "historical", "armour")
        self.assertEqual(result["armour"], "armour_row")

    def test_raises_last_error_when_none_found(self) -> None:
        rows: list[dict] = []
        with self.assertRaises(ValueError):
            _find_variant_any(rows, ["key_a", "key_b"], None, "armour")

    def test_returns_first_match(self) -> None:
        rows = [{"ceos_key": "key_a", "armour": "armour_a", "game_mode": None}]
        result = _find_variant_any(rows, ["key_a", "key_b"], None, "armour")
        self.assertEqual(result["armour"], "armour_a")


class RequireRowWithTableTest(unittest.TestCase):
    def test_finds_row_and_returns_table_name(self) -> None:
        rows = [("db/melee_weapons_tables/data__", {"key": "weapon_x", "damage": 100})]
        table_name, row = _require_row_with_table(rows, "weapon_x", "damage")
        self.assertEqual(table_name, "db/melee_weapons_tables/data__")
        self.assertEqual(row["damage"], 100)

    def test_raises_when_row_is_missing(self) -> None:
        rows = [("db/melee_weapons_tables/data__", {"key": "weapon_y", "damage": 50})]
        with self.assertRaises(ValueError) as ctx:
            _require_row_with_table(rows, "weapon_x", "damage")
        self.assertIn("Stat row is missing", str(ctx.exception))

    def test_raises_when_column_is_missing(self) -> None:
        rows = [("db/melee_weapons_tables/data__", {"key": "weapon_x"})]
        with self.assertRaises(ValueError) as ctx:
            _require_row_with_table(rows, "weapon_x", "damage")
        self.assertIn("Column is missing", str(ctx.exception))

    def test_raises_when_column_is_not_numeric(self) -> None:
        rows = [("db/melee_weapons_tables/data__", {"key": "weapon_x", "damage": "bad"})]
        with self.assertRaises(ValueError) as ctx:
            _require_row_with_table(rows, "weapon_x", "damage", numeric=True)
        self.assertIn("not numeric", str(ctx.exception))

    def test_non_numeric_check_skipped_when_numeric_false(self) -> None:
        rows = [("db/t/d", {"key": "weapon_x", "audio_type": "metal"})]
        _, row = _require_row_with_table(rows, "weapon_x", "audio_type", numeric=False)
        self.assertEqual(row["audio_type"], "metal")


class ResolveStatTargetTest(unittest.TestCase):
    def _melee_session(self) -> Any:
        return _mock_session({
            "ceos_to_equipment_variants_weapons": [
                {"ceos_key": "key_weapon", "primary_melee_weapon": "melee_row", "game_mode": "historical"},
            ],
            "melee_weapons": [
                {"key": "melee_row", "damage": 100},
            ],
            "ceos_to_equipment_variants_armours": [],
            "unit_armour_types": [],
            "missile_weapons": [],
            "projectiles": [],
            "land_units": [],
            "main_units": [],
        })

    def _armour_session(self) -> Any:
        return _mock_session({
            "ceos_to_equipment_variants_armours": [
                {"ceos_key": "key_armour", "armour": "armour_row", "game_mode": "historical"},
            ],
            "unit_armour_types": [
                {"key": "armour_row", "armour_value": 60, "audio_type": "metal"},
            ],
            "ceos_to_equipment_variants_weapons": [],
            "melee_weapons": [],
            "missile_weapons": [],
            "projectiles": [],
            "land_units": [],
            "main_units": [],
        })

    def _projectile_session(self) -> Any:
        return _mock_session({
            "ceos_to_equipment_variants_weapons": [
                {"ceos_key": "key_bow", "primary_missile_weapon": "missile_row", "game_mode": "historical"},
            ],
            "missile_weapons": [
                {"key": "missile_row", "default_projectile": "proj_row"},
            ],
            "projectiles": [
                {"key": "proj_row", "ap_damage": 900},
            ],
            "ceos_to_equipment_variants_armours": [],
            "unit_armour_types": [],
            "melee_weapons": [],
            "land_units": [],
            "main_units": [],
        })

    def _land_unit_session(self) -> Any:
        return _mock_session({
            "land_units": [
                {"key": "unit_key", "charge_bonus": 150},
            ],
            "main_units": [],
            "ceos_to_equipment_variants_weapons": [],
            "ceos_to_equipment_variants_armours": [],
            "melee_weapons": [],
            "missile_weapons": [],
            "projectiles": [],
            "unit_armour_types": [],
        })

    def test_resolves_melee_weapon_stat(self) -> None:
        session = self._melee_session()
        target = resolve_stat_target(session, "key_weapon", "melee_weapon", "damage", 200, "historical")
        self.assertEqual(target.row_key, "melee_row")
        self.assertEqual(target.column, "damage")
        self.assertEqual(target.value, 200)

    def test_resolves_armour_stat(self) -> None:
        session = self._armour_session()
        target = resolve_stat_target(session, "key_armour", "armour", "armour_value", 90, "historical")
        self.assertEqual(target.row_key, "armour_row")
        self.assertEqual(target.column, "armour_value")

    def test_resolves_armour_audio_type_string_column(self) -> None:
        session = self._armour_session()
        target = resolve_stat_target(session, "key_armour", "armour", "audio_type", "leather", "historical")
        self.assertEqual(target.row_key, "armour_row")
        self.assertEqual(target.value, "leather")

    def test_resolves_direct_unit_armour_row_key_without_variant_lookup(self) -> None:
        session = self._armour_session()
        target = resolve_stat_target(session, "armour_row", "armour", "armour_value", 80, None)
        self.assertEqual(target.table_name, "unit_armour_types")
        self.assertEqual(target.row_key, "armour_row")
        self.assertEqual(target.value, 80)

    def test_resolves_projectile_stat(self) -> None:
        session = self._projectile_session()
        target = resolve_stat_target(session, "key_bow", "projectile", "ap_damage", 999, "historical")
        self.assertEqual(target.row_key, "proj_row")
        self.assertEqual(target.value, 999)

    def test_resolves_land_unit_stat(self) -> None:
        session = self._land_unit_session()
        target = resolve_stat_target(session, "unit_key", "land_unit", "charge_bonus", 222, None)
        self.assertEqual(target.row_key, "unit_key")
        self.assertEqual(target.value, 222)

    def test_raises_for_unsupported_stat_table(self) -> None:
        session = self._melee_session()
        with self.assertRaises(ValueError) as ctx:
            resolve_stat_target(session, "key_weapon", "invalid_table", "damage", 10, None)
        self.assertIn("Unsupported statTable", str(ctx.exception))

    def test_raises_for_unsupported_column(self) -> None:
        session = self._melee_session()
        with self.assertRaises(ValueError) as ctx:
            resolve_stat_target(session, "key_weapon", "melee_weapon", "nonexistent_col", 10, None)
        self.assertIn("not allowed", str(ctx.exception))

    def test_ancilliary_spelling_is_resolved_for_armour(self) -> None:
        # Session stores key with 'ancilliary' (typo) but we query with 'ancillary'
        session = _mock_session({
            "ceos_to_equipment_variants_armours": [
                {"ceos_key": "3k_mtu_ancilliary_armour_x", "armour": "armour_row", "game_mode": "historical"},
            ],
            "unit_armour_types": [
                {"key": "armour_row", "armour_value": 50},
            ],
            "ceos_to_equipment_variants_weapons": [],
            "melee_weapons": [],
            "missile_weapons": [],
            "projectiles": [],
            "land_units": [],
            "main_units": [],
        })
        target = resolve_stat_target(session, "3k_mtu_ancillary_armour_x", "armour", "armour_value", 80, "historical")
        self.assertEqual(target.row_key, "armour_row")


if __name__ == "__main__":
    unittest.main()
